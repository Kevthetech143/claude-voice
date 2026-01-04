"""LLM provider protocol"""

from typing import Protocol, AsyncIterator


class LLMProvider(Protocol):
    """Protocol for LLM providers"""

    async def query_stream(self, text: str) -> AsyncIterator[str]:
        """
        Query LLM with streaming response

        Args:
            text: User query text

        Yields:
            Token strings as they're generated

        Example:
            async for token in llm.query_stream("Hello"):
                print(token, end="", flush=True)
        """
        ...
