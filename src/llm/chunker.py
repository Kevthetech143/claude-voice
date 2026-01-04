"""
Sentence chunker for streaming TTS
Buffers tokens and emits complete sentences for parallel TTS processing
"""

from typing import AsyncIterator

from ..core.events import EventObserver, EventType


class SentenceChunker:
    """
    Buffers streaming tokens and emits complete sentences

    This enables starting TTS on the first sentence while the LLM continues generating.
    Key optimization for perceived latency.
    """

    def __init__(
        self,
        min_sentence_length: int = 10,
        observer: EventObserver | None = None,
    ):
        """
        Args:
            min_sentence_length: Minimum characters before emitting a sentence
            observer: Event observer for monitoring
        """
        self.min_sentence_length = min_sentence_length
        self.observer = observer

        # Sentence terminators
        self.terminators = {".", "!", "?"}

        # Common abbreviations that shouldn't split sentences
        self.abbreviations = {
            "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.",
            "i.e.", "e.g.", "etc.", "vs.", "inc.", "ltd.", "corp.",
        }

    async def chunk_stream(self, token_stream: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        Process streaming tokens and yield complete sentences

        Args:
            token_stream: Async iterator of tokens from LLM

        Yields:
            Complete sentences

        Example:
            async for sentence in chunker.chunk_stream(llm.query_stream("Hello")):
                await tts.speak(sentence)
        """
        buffer = ""

        async for token in token_stream:
            buffer += token

            # Check if we have a sentence terminator
            if self._has_sentence_boundary(buffer):
                # Extract the sentence
                sentence = self._extract_sentence(buffer)

                if sentence and len(sentence) >= self.min_sentence_length:
                    if self.observer:
                        self.observer.emit(
                            EventType.SENTENCE_READY,
                            {"sentence": sentence[:100], "length": len(sentence)},
                        )

                    yield sentence

                    # Remove the sentence from buffer
                    buffer = buffer[len(sentence):].lstrip()

        # Yield any remaining content as final sentence
        if buffer.strip():
            final_sentence = buffer.strip()
            if self.observer:
                self.observer.emit(
                    EventType.SENTENCE_READY,
                    {
                        "sentence": final_sentence[:100],
                        "length": len(final_sentence),
                        "final": True,
                    },
                )
            yield final_sentence

    def _has_sentence_boundary(self, text: str) -> bool:
        """Check if text contains a sentence boundary"""
        return any(term in text for term in self.terminators)

    def _extract_sentence(self, text: str) -> str:
        """
        Extract the first complete sentence from text

        Handles:
        - Multiple terminators (., !, ?)
        - Abbreviations (Dr., etc.)
        - Proper spacing
        """
        # Find all terminator positions
        positions = []
        for i, char in enumerate(text):
            if char in self.terminators:
                positions.append(i)

        if not positions:
            return ""

        # Check each position to see if it's a true sentence boundary
        for pos in positions:
            # Get context around terminator
            sentence = text[: pos + 1].strip()

            # Check if it's an abbreviation
            lower_sentence = sentence.lower()
            if any(lower_sentence.endswith(abbr) for abbr in self.abbreviations):
                continue

            # Check minimum length
            if len(sentence) < self.min_sentence_length:
                continue

            # This is a valid sentence boundary
            return sentence

        # No valid boundary found
        return ""

    def chunk_text(self, text: str) -> list[str]:
        """
        Synchronous version for testing
        Splits text into sentences

        Args:
            text: Complete text to split

        Returns:
            List of sentences
        """
        sentences = []
        buffer = text

        while self._has_sentence_boundary(buffer):
            sentence = self._extract_sentence(buffer)

            if sentence and len(sentence) >= self.min_sentence_length:
                sentences.append(sentence)
                buffer = buffer[len(sentence):].lstrip()
            else:
                # No more valid sentences
                break

        # Add remaining text if any
        if buffer.strip():
            sentences.append(buffer.strip())

        return sentences
