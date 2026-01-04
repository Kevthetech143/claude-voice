"""
STT provider protocol
Defines interface for all STT implementations
"""

from typing import Protocol, Optional
from ..audio.types import AudioData
from ..core.events import EventObserver


class STTProvider(Protocol):
    """
    Protocol for Speech-to-Text providers

    All STT implementations must follow this interface for
    dependency injection and testing
    """

    async def transcribe(
        self,
        audio: AudioData,
        observer: Optional[EventObserver] = None
    ) -> str:
        """
        Transcribe audio to text

        Args:
            audio: Audio data to transcribe
            observer: Optional event observer for monitoring

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription fails
        """
        ...
