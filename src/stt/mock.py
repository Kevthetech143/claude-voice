"""
Mock STT implementation for testing
Returns predefined text without requiring API calls
"""

import asyncio
from typing import Optional
from ..audio.types import AudioData
from ..core.events import EventObserver, EventType


class MockSTT:
    """
    Mock STT for AI testing

    Returns predefined text instead of calling Whisper API
    Enables testing without API costs or network dependencies
    """

    def __init__(self, transcription: str = "This is a test transcription"):
        """
        Initialize mock STT

        Args:
            transcription: Text to return from transcribe()
        """
        self.transcription = transcription
        self.call_count = 0
        self.last_audio: Optional[AudioData] = None

    async def transcribe(
        self,
        audio: AudioData,
        observer: Optional[EventObserver] = None
    ) -> str:
        """
        Mock transcription - returns predefined text

        Args:
            audio: Audio data (ignored, but recorded for testing)
            observer: Optional event observer

        Returns:
            Predefined transcription text
        """
        self.call_count += 1
        self.last_audio = audio

        # Emit start event
        if observer:
            observer.emit(
                EventType.STT_START,
                {
                    "audio_duration_ms": audio.duration_ms,
                    "audio_size_kb": audio.size_kb,
                    "format": audio.format.value,
                    "mock": True
                }
            )

        # Simulate API latency (100ms)
        await asyncio.sleep(0.1)

        # Emit complete event
        if observer:
            observer.emit(
                EventType.STT_COMPLETE,
                {
                    "text": self.transcription,
                    "latency_ms": 100.0,
                    "text_length": len(self.transcription),
                    "mock": True
                }
            )

        return self.transcription

    def reset(self) -> None:
        """Reset call tracking"""
        self.call_count = 0
        self.last_audio = None


class DynamicMockSTT:
    """
    Mock STT with dynamic responses

    Useful for testing conversations with multiple turns
    """

    def __init__(self, responses: list[str]):
        """
        Initialize with list of responses

        Args:
            responses: List of transcriptions to return in order
        """
        self.responses = responses
        self.current_index = 0
        self.call_count = 0

    async def transcribe(
        self,
        audio: AudioData,
        observer: Optional[EventObserver] = None
    ) -> str:
        """
        Return next transcription from list

        Args:
            audio: Audio data (ignored)
            observer: Optional event observer

        Returns:
            Next transcription from responses list
        """
        self.call_count += 1

        # Get current response and advance
        response = self.responses[self.current_index % len(self.responses)]
        self.current_index += 1

        # Emit events
        if observer:
            observer.emit(EventType.STT_START, {"mock": True})

        await asyncio.sleep(0.1)  # Simulate latency

        if observer:
            observer.emit(
                EventType.STT_COMPLETE,
                {"text": response, "latency_ms": 100.0, "mock": True}
            )

        return response

    def reset(self) -> None:
        """Reset to first response"""
        self.current_index = 0
        self.call_count = 0
