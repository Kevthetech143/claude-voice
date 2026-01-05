"""
Claude Code CLI integration for voice assistant
Uses --print --output-format stream-json for full Claude Code features

Includes explicit MCP server and CLAUDE.md loading via:
- --mcp-config .mcp.json (project MCP servers: brave-search, hivemind)
- --setting-sources user,project (CLAUDE.md from both scopes)
- --chrome (browser automation via Chrome extension)

CORRECTED by BETA - All 6 flaws fixed
ENHANCED by ALPHA - MCP, CLAUDE.md, and Chrome access added
"""

import asyncio
import subprocess
import json
import uuid
import logging
from typing import AsyncIterator, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ClaudeCodeSession:
    """
    Interface to Claude Code CLI with full MCP/CLAUDE.md/Chrome support

    Uses stream-json output format for real-time streaming while maintaining
    full access to MCP tools, skills, CLAUDE.md configuration, and Chrome browser control.

    MCP servers loaded via --mcp-config .mcp.json (project-scoped)
    CLAUDE.md loaded via --setting-sources user,project
    Chrome automation enabled via --chrome flag (requires Chrome extension)
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
        observer=None,
        timeout_seconds: int = 120
    ):
        """
        Initialize Claude Code session

        Args:
            session_id: UUID for session persistence (auto-generated if None)
            system_message: Optional system prompt (uses --system-prompt)
            observer: Event observer for monitoring
            timeout_seconds: Max time for single query (default: 120s)
        """
        self.session_id = session_id or str(uuid.uuid4())
        self.system_message = system_message
        self.observer = observer
        self.turn_count = 0
        self.total_cost_usd = 0.0
        self.timeout_seconds = timeout_seconds

        logger.info(f"ClaudeCodeSession initialized: {self.session_id}")

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Stream response from Claude Code CLI

        Args:
            text: User input text

        Yields:
            Text chunks as they arrive (multiple assistant messages possible)

        Raises:
            TimeoutError: If query exceeds timeout_seconds
            RuntimeError: If Claude Code crashes

        Note:
            - First call creates session
            - Subsequent calls MUST use --continue for history
            - Full MCP tools available
            - CLAUDE.md config loaded automatically
        """
        if self.observer:
            self.observer.emit("llm_query_start", {"input": text})

        try:
            # Stream with timeout protection
            # Note: We can't timeout an async generator directly with wait_for
            # Instead, we timeout individual reads inside _stream_response
            async for chunk in self._stream_response(text):
                yield chunk

            self.turn_count += 1

        except asyncio.TimeoutError:
            logger.error(f"Query timeout after {self.timeout_seconds}s")
            if self.observer:
                self.observer.emit("llm_error", {
                    "error": "timeout",
                    "timeout_seconds": self.timeout_seconds
                })
            raise TimeoutError(f"Query timed out after {self.timeout_seconds}s")

        except Exception as e:
            logger.error(f"Query failed: {e}")
            if self.observer:
                self.observer.emit("llm_error", {"error": str(e)})
            raise

    async def _stream_response(self, text: str) -> AsyncIterator[str]:
        """Internal streaming implementation"""

        import time
        deadline = time.time() + self.timeout_seconds

        # Build command with full MCP and CLAUDE.md support
        cmd = [
            "claude",
            "--print",
            "--output-format", "stream-json",
            "--verbose",
            "--model", "sonnet",  # Force Sonnet 4.5 (not Haiku)
            "--permission-mode", "bypassPermissions",  # Full autonomy - no permission prompts
            "--mcp-config", ".mcp.json",  # Load project MCP servers
            "--setting-sources", "user,project",  # Load CLAUDE.md from both scopes
            "--chrome",  # Enable browser automation via Chrome extension
        ]

        # CRITICAL: Session management
        # Turn 0: Create new session with --session-id --fork-session
        # Turn 1+: Continue most recent with just --continue (no session-id to avoid locking)
        if self.turn_count == 0:
            cmd.extend(["--session-id", self.session_id, "--fork-session"])
        else:
            cmd.append("--continue")

        # Add system message if provided
        if self.system_message:
            cmd.extend(["--system-prompt", self.system_message])

        logger.debug(f"Running: {' '.join(cmd)}")

        # Start process with large buffer for Chrome tool outputs (screenshots, HTML)
        # Default limit is ~64KB, Chrome can return megabytes of base64 data
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=10 * 1024 * 1024  # 10MB buffer for large Chrome tool outputs
        )

        try:
            # Send input
            process.stdin.write((text + "\n").encode())
            await process.stdin.drain()
            process.stdin.close()

            # Stream output
            response_text = []
            in_tool_execution = False

            while True:
                # Check timeout
                if time.time() > deadline:
                    raise asyncio.TimeoutError(f"Query exceeded {self.timeout_seconds}s")

                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    data = json.loads(line.decode())

                    # Handle different message types
                    msg_type = data.get("type")

                    if msg_type == "system":
                        # Session initialization
                        logger.debug(f"Session init: {data.get('session_id')}")

                    elif msg_type == "assistant":
                        # Assistant response
                        message = data.get("message", {})
                        content = message.get("content", [])

                        for block in content:
                            block_type = block.get("type")

                            if block_type == "text":
                                # Text content - yield it
                                text_chunk = block["text"]
                                response_text.append(text_chunk)

                                if self.observer:
                                    self.observer.emit("llm_token_received", {"text": text_chunk})

                                # Yield full text (chunker will split into sentences)
                                yield text_chunk

                            elif block_type == "tool_use":
                                # Tool execution starting
                                tool_name = block.get("name", "unknown")
                                in_tool_execution = True

                                logger.debug(f"Tool execution: {tool_name}")

                                # Emit tool start event
                                if self.observer:
                                    self.observer.emit("llm_token_received", {
                                        "text": f"[Using {tool_name}...]",
                                        "tool": True
                                    })

                                # Optional: Yield status for TTS
                                # yield f"[Using {tool_name}...]"

                    elif msg_type == "user":
                        # Tool result injected by Claude Code (automatic)
                        in_tool_execution = False

                        logger.debug("Tool execution complete")

                    elif msg_type == "result":
                        # Final result with metrics
                        usage = data.get("usage", {})
                        cost = data.get("total_cost_usd", 0.0)
                        self.total_cost_usd += cost

                        logger.info(f"Turn {self.turn_count + 1} complete: ${cost:.4f}")

                        if self.observer:
                            self.observer.emit("llm_complete", {
                                "cost_usd": cost,
                                "total_cost_usd": self.total_cost_usd,
                                "usage": usage,
                                "response": "".join(response_text)
                            })

                        break  # Done

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON line: {e}")
                    continue

            # Wait for process to complete
            await process.wait()

            if process.returncode != 0:
                # Read stderr for error details
                stderr = await process.stderr.read()
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Claude Code exited with code {process.returncode}: {error_msg}")
                raise RuntimeError(f"Claude Code process failed ({process.returncode}): {error_msg}")

        except Exception as e:
            logger.error(f"Error in _stream_response: {e}")
            raise

        finally:
            # Ensure process is terminated
            if process.returncode is None:
                process.kill()
                await process.wait()

    def get_metrics(self) -> dict:
        """
        Get session metrics

        Returns:
            Dict with turn_count, total_cost_usd, session_id
        """
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "total_cost_usd": self.total_cost_usd,
            "provider": "claude-code-cli",
            "timeout_seconds": self.timeout_seconds
        }

    def reset(self):
        """Reset session (creates new session ID)"""
        self.session_id = str(uuid.uuid4())
        self.turn_count = 0
        self.total_cost_usd = 0.0
        logger.info(f"Session reset: {self.session_id}")
