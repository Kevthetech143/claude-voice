"""
Claude integration via official Anthropic API
Production-ready implementation with streaming and conversation history
"""

import asyncio
from typing import AsyncIterator
from anthropic import AsyncAnthropic

from ..core.events import EventObserver, EventType


class ClaudeAPI:
    """
    Production Claude integration using official Anthropic SDK

    Features:
    - Token streaming for low latency
    - Conversation history management
    - Proper error handling and timeouts
    - Cancellation safety
    - Event observability
    """

    # Maximum conversation history to prevent memory leaks
    MAX_HISTORY_TURNS = 50

    def __init__(
        self,
        api_key: str,
        system_prompt: str = "You are a helpful voice assistant. Keep responses SHORT and conversational (2-3 sentences max).",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 1024,
        timeout: float = 15.0,  # Reduced from 30s for voice UX
        first_token_timeout: float = 5.0,  # Aggressive timeout for first token
        observer: EventObserver | None = None,
    ):
        """
        Args:
            api_key: Anthropic API key
            system_prompt: System prompt for the assistant
            model: Claude model to use
            max_tokens: Maximum tokens in response
            timeout: Total timeout for API calls (seconds) - voice optimized
            first_token_timeout: Timeout for first token (seconds) - aggressive
            observer: Event observer for monitoring
        """
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.first_token_timeout = first_token_timeout
        self.observer = observer

        # Bounded conversation history (prevents memory leaks)
        self.conversation_history: list[dict[str, str]] = []

        # API client (created on first use)
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        """Get or create API client"""
        if self._client is None:
            self._client = AsyncAnthropic(
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Query Claude with streaming response

        Args:
            text: User query

        Yields:
            Tokens as they're generated

        Raises:
            anthropic.APIError: On API errors
            asyncio.TimeoutError: On timeout
            asyncio.CancelledError: On cancellation
        """
        if self.observer:
            self.observer.emit(EventType.LLM_QUERY_START, {"query": text[:100]})

        try:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": text
            })

            # Trim history to prevent memory leaks (keep last MAX_HISTORY_TURNS messages)
            if len(self.conversation_history) > self.MAX_HISTORY_TURNS:
                self.conversation_history = self.conversation_history[-self.MAX_HISTORY_TURNS:]

            client = self._get_client()

            first_token = True
            total_tokens = 0
            assistant_response = ""

            # Stream response with timeout
            try:
                async with asyncio.timeout(self.timeout):
                    async with client.messages.stream(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        system=self.system_prompt,
                        messages=self.conversation_history,
                    ) as stream:
                        async for text_chunk in stream.text_stream:
                            total_tokens += 1
                            assistant_response += text_chunk

                            if first_token and self.observer:
                                self.observer.emit(
                                    EventType.LLM_TOKEN_RECEIVED,
                                    {"token": text_chunk[:50]}
                                )
                                first_token = False

                            yield text_chunk

            except asyncio.TimeoutError:
                if self.observer:
                    self.observer.emit(
                        EventType.LLM_ERROR,
                        {"error": "Timeout", "timeout_seconds": self.timeout}
                    )
                raise

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })

            if self.observer:
                self.observer.emit(
                    EventType.LLM_COMPLETE,
                    {
                        "total_tokens": total_tokens,
                        "response_length": len(assistant_response)
                    }
                )

        except asyncio.CancelledError:
            # Clean cancellation
            if self.observer:
                self.observer.emit(
                    EventType.LLM_ERROR,
                    {"error": "Cancelled"}
                )
            raise

        except Exception as e:
            if self.observer:
                self.observer.emit(
                    EventType.LLM_ERROR,
                    {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "query_length": len(text),
                        "conversation_turn": len(self.conversation_history),
                        "model": self.model,
                    }
                )
            raise

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history.clear()

    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history"""
        return self.conversation_history.copy()

    async def close(self) -> None:
        """Close API client"""
        if self._client is not None:
            await self._client.close()
            self._client = None
