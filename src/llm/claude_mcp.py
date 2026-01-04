"""
Claude integration via MCP (Model Context Protocol)
Uses the user's existing Claude Code subscription
"""

import asyncio
import subprocess
import json
from typing import AsyncIterator

from ..core.events import EventObserver, EventType


class ClaudeMCP:
    """
    Claude integration using MCP
    This uses the user's existing Claude Code subscription - no separate API key needed
    """

    def __init__(
        self,
        system_prompt: str = "You are a helpful voice assistant.",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 1024,
        observer: EventObserver | None = None,
    ):
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.observer = observer

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Query Claude via MCP with token streaming

        This executes `claude code` CLI in streaming mode and parses output.
        The CLI uses the user's existing subscription.

        Args:
            text: User query

        Yields:
            Tokens as they're generated
        """
        if self.observer:
            self.observer.emit(EventType.LLM_QUERY_START, {"query": text[:100]})

        try:
            # Build the prompt
            full_prompt = f"{self.system_prompt}\n\nUser: {text}\n\nAssistant:"

            # Execute claude code CLI
            # Note: This is a simplified implementation
            # TODO: Replace with proper MCP protocol client
            process = await asyncio.create_subprocess_exec(
                "claude",
                "code",
                "--model",
                self.model,
                "--max-tokens",
                str(self.max_tokens),
                "--stream",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send prompt
            if process.stdin:
                process.stdin.write(full_prompt.encode())
                await process.stdin.drain()
                process.stdin.close()

            # Stream output
            first_token = True
            total_tokens = 0

            if process.stdout:
                async for line in process.stdout:
                    token = line.decode().rstrip("\n")

                    if token:
                        total_tokens += 1

                        if first_token and self.observer:
                            self.observer.emit(
                                EventType.LLM_TOKEN_RECEIVED, {"token": token[:50]}
                            )
                            first_token = False

                        yield token

            await process.wait()

            if self.observer:
                self.observer.emit(
                    EventType.LLM_COMPLETE, {"total_tokens": total_tokens}
                )

        except Exception as e:
            if self.observer:
                self.observer.emit(
                    EventType.LLM_ERROR, {"error": str(e), "error_type": type(e).__name__}
                )
            raise


class ClaudeAPI:
    """
    Alternative: Direct Anthropic API integration
    Requires ANTHROPIC_API_KEY environment variable
    Use this if MCP integration proves complex
    """

    def __init__(
        self,
        api_key: str,
        system_prompt: str = "You are a helpful voice assistant.",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 1024,
        observer: EventObserver | None = None,
    ):
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.observer = observer

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Query Claude via direct API with streaming

        Note: This requires a separate API key (costs money)
        Prefer ClaudeMCP for using existing subscription
        """
        try:
            # Import here to make it optional
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.api_key)

            if self.observer:
                self.observer.emit(EventType.LLM_QUERY_START, {"query": text[:100]})

            first_token = True
            total_tokens = 0

            async with client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.system_prompt,
                messages=[{"role": "user", "content": text}],
            ) as stream:
                async for text_chunk in stream.text_stream:
                    total_tokens += 1

                    if first_token and self.observer:
                        self.observer.emit(
                            EventType.LLM_TOKEN_RECEIVED, {"token": text_chunk[:50]}
                        )
                        first_token = False

                    yield text_chunk

            if self.observer:
                self.observer.emit(
                    EventType.LLM_COMPLETE, {"total_tokens": total_tokens}
                )

        except Exception as e:
            if self.observer:
                self.observer.emit(
                    EventType.LLM_ERROR, {"error": str(e), "error_type": type(e).__name__}
                )
            raise
