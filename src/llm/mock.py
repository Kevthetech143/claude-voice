"""Mock LLM for testing"""

import asyncio
from typing import AsyncIterator

from ..core.events import EventObserver, EventType


class MockLLM:
    """
    Mock LLM that returns predefined responses
    Perfect for AI-driven testing without API calls
    """

    def __init__(
        self,
        response: str = "Hello! I'm Claude, your voice assistant. How can I help you today?",
        token_delay_ms: int = 10,  # Simulate streaming delay
        observer: EventObserver | None = None,
    ):
        """
        Args:
            response: Predefined response to return
            token_delay_ms: Delay between tokens to simulate streaming
            observer: Event observer
        """
        self.response = response
        self.token_delay_ms = token_delay_ms
        self.observer = observer

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Return predefined response as token stream

        Args:
            text: User query (ignored in mock)

        Yields:
            Tokens from predefined response
        """
        if self.observer:
            self.observer.emit(EventType.LLM_QUERY_START, {"query": text[:100]})

        # Tokenize response (simple word-based splitting)
        tokens = self._tokenize(self.response)

        first_token = True
        for token in tokens:
            if self.token_delay_ms > 0:
                await asyncio.sleep(self.token_delay_ms / 1000)

            if first_token and self.observer:
                self.observer.emit(EventType.LLM_TOKEN_RECEIVED, {"token": token[:50]})
                first_token = False

            yield token

        if self.observer:
            self.observer.emit(EventType.LLM_COMPLETE, {"total_tokens": len(tokens)})

    def _tokenize(self, text: str) -> list[str]:
        """
        Simple tokenization for realistic streaming
        Returns word tokens with spaces and punctuation
        """
        tokens = []
        words = text.split()

        for i, word in enumerate(words):
            if i > 0:
                tokens.append(" ")  # Add space before word
            tokens.append(word)

        return tokens


class ConfigurableMockLLM:
    """
    Mock LLM with configurable responses based on input
    Useful for testing different conversation flows
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default_response: str = "I don't understand.",
        observer: EventObserver | None = None,
    ):
        """
        Args:
            responses: Map of query patterns to responses
            default_response: Fallback response
            observer: Event observer
        """
        self.responses = responses or {}
        self.default_response = default_response
        self.observer = observer

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """Return response based on query pattern matching"""
        # Find matching response
        response = self.default_response
        text_lower = text.lower()

        for pattern, resp in self.responses.items():
            if pattern.lower() in text_lower:
                response = resp
                break

        # Stream the response
        mock = MockLLM(response=response, observer=self.observer)
        async for token in mock.query_stream(text):
            yield token
