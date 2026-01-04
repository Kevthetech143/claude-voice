"""
TTS provider protocol
Defines interface for all TTS implementations
"""

from typing import Protocol, Optional
from ..audio.types import AudioData
from ..core.events import EventObserver


class TTSProvider(Protocol):
    """
    Protocol for Text-to-Speech providers

    All TTS implementations must follow this interface for
    dependency injection and testing
    """

    async def speak(
        self,
        text: str,
        observer: Optional[EventObserver] = None
    ) -> AudioData:
        """
        Convert text to speech

        Args:
            text: Text to convert to speech
            observer: Optional event observer for monitoring

        Returns:
            AudioData containing synthesized speech

        Raises:
            Exception: If speech synthesis fails
        """
        ...
