"""
Improved sentence chunker with edge case handling
Handles quotes, decimals, URLs, ellipsis, abbreviations
"""

import re
from typing import AsyncIterator

from ..core.events import EventObserver, EventType


class SentenceChunker:
    """
    Production-grade sentence chunker for streaming TTS

    Handles edge cases:
    - Quoted speech: "Hello!" she said.
    - Decimals: The value is 3.14.
    - URLs: Visit www.example.com.
    - Ellipsis: Wait... let me think.
    - Abbreviations: Dr. Smith said...
    - Multiple punctuation: Really?!
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

        # Sentence boundary detection pattern
        # Matches: . ! ? followed by space/newline/end, but NOT in special cases
        self.sentence_pattern = re.compile(
            r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s+(?=[A-Z])|(?<=\.|\?|!)$'
        )

        # Common abbreviations that don't end sentences
        self.abbreviations = {
            "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
            "i.e", "e.g", "etc", "vs", "inc", "ltd", "corp",
            "st", "ave", "blvd", "dept", "fig", "vol", "no",
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

            # Try to extract sentences
            sentences = self._extract_sentences(buffer)

            if sentences:
                # Emit all complete sentences except the last fragment
                for sentence in sentences[:-1]:
                    if len(sentence) >= self.min_sentence_length:
                        if self.observer:
                            self.observer.emit(
                                EventType.SENTENCE_READY,
                                {"sentence": sentence[:100], "length": len(sentence)},
                            )
                        yield sentence

                # Keep the last fragment in buffer
                buffer = sentences[-1]

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

    def _extract_sentences(self, text: str) -> list[str]:
        """
        Extract complete sentences from text

        Uses regex-based detection with edge case handling

        Args:
            text: Text to split

        Returns:
            List of sentence fragments (last one may be incomplete)
        """
        if not text:
            return []

        # Handle edge cases first

        # 1. Check if we're inside quotes (don't split mid-quote)
        if self._is_inside_quotes(text):
            return [text]  # Keep buffering

        # 2. Check if last terminator is part of decimal (3.14)
        if self._ends_with_decimal(text):
            return [text]  # Keep buffering

        # 3. Check if last terminator is part of URL (www.example.com)
        if self._ends_with_url(text):
            return [text]  # Keep buffering

        # 4. Check if last terminator is ellipsis (...) in middle of thought
        if self._ends_with_incomplete_ellipsis(text):
            return [text]  # Keep buffering

        # 5. Check if last terminator is abbreviation (Dr. Smith)
        if self._ends_with_abbreviation(text):
            return [text]  # Keep buffering

        # Split by sentence boundaries
        # Use a simple but effective approach: split on terminator + whitespace
        sentences = []
        current = ""

        for char in text:
            current += char

            # Check if we hit a sentence boundary
            if char in ".!?" and len(current) >= self.min_sentence_length:
                # Peek ahead - is next char uppercase or end of string?
                remaining = text[len(current):]

                if not remaining or (remaining[0].isspace() and len(remaining) > 1 and remaining[1].isupper()):
                    # Valid sentence boundary
                    if not self._is_false_boundary(current):
                        sentences.append(current.strip())
                        current = ""

        # Add remaining text
        if current:
            sentences.append(current)

        return sentences if sentences else [text]

    def _is_inside_quotes(self, text: str) -> bool:
        """Check if text ends inside quotes"""
        # Count unmatched quotes
        double_quotes = text.count('"') % 2
        single_quotes = text.count("'") % 2

        return double_quotes != 0 or single_quotes != 0

    def _ends_with_decimal(self, text: str) -> bool:
        """Check if text ends with decimal number (3.14)"""
        decimal_pattern = r'\d+\.\d*$'
        return bool(re.search(decimal_pattern, text))

    def _ends_with_url(self, text: str) -> bool:
        """Check if text ends with URL"""
        url_pattern = r'(www\.|https?://)[^\s]*\.?$'
        return bool(re.search(url_pattern, text, re.IGNORECASE))

    def _ends_with_incomplete_ellipsis(self, text: str) -> bool:
        """Check if text ends with incomplete ellipsis"""
        # One or two dots that might become three
        return text.endswith('.') or text.endswith('..')

    def _ends_with_abbreviation(self, text: str) -> bool:
        """Check if text ends with common abbreviation"""
        text_lower = text.lower().rstrip()

        for abbr in self.abbreviations:
            if text_lower.endswith(abbr + '.'):
                return True

        return False

    def _is_false_boundary(self, sentence: str) -> bool:
        """Check if sentence ending is a false boundary"""
        sentence_lower = sentence.lower().strip()

        # Check abbreviations
        for abbr in self.abbreviations:
            if sentence_lower.endswith(abbr + '.'):
                return True

        # Check decimals
        if self._ends_with_decimal(sentence):
            return True

        # Check URLs
        if self._ends_with_url(sentence):
            return True

        return False

    def chunk_text(self, text: str) -> list[str]:
        """
        Synchronous version for testing

        Args:
            text: Complete text to split

        Returns:
            List of sentences
        """
        sentences = []
        buffer = text

        while True:
            extracted = self._extract_sentences(buffer)

            if len(extracted) <= 1:
                # No more complete sentences
                break

            # Take first sentence
            sentence = extracted[0]
            if len(sentence) >= self.min_sentence_length:
                sentences.append(sentence)

            # Remove from buffer
            buffer = buffer[len(sentence):].lstrip()

        # Add remaining
        if buffer.strip():
            sentences.append(buffer.strip())

        return sentences
