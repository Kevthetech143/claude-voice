"""
Mock TTS implementation for testing
Logs text instead of generating audio
"""

import asyncio
from typing import Optional
from ..audio.types import AudioData, AudioFormat
from ..core.events import EventObserver, EventType


class MockTTS:
    """
    Mock TTS for AI testing

    Instead of generating audio, logs the text
    Returns silent audio data for pipeline testing
    """

    def __init__(self, simulate_latency_ms: float = 50.0):
        """
        Initialize mock TTS

        Args:
            simulate_latency_ms: Latency to simulate (default 50ms)
        """
        self.simulate_latency_ms = simulate_latency_ms
        self.call_count = 0
        self.spoken_texts: list[str] = []

    async def speak(
        self,
        text: str,
        observer: Optional[EventObserver] = None
    ) -> AudioData:
        """
        Mock speech synthesis - logs text and returns silent audio

        Args:
            text: Text to "speak"
            observer: Optional event observer

        Returns:
            AudioData with silent audio
        """
        self.call_count += 1
        self.spoken_texts.append(text)

        # Emit start event
        if observer:
            observer.emit(
                EventType.TTS_START,
                {
                    "text": text,
                    "text_length": len(text),
                    "mock": True
                }
            )

        # Simulate TTS latency
        await asyncio.sleep(self.simulate_latency_ms / 1000.0)

        # Generate silent audio
        # Estimate duration based on text length (~150 words/min)
        word_count = len(text.split())
        estimated_duration_ms = (word_count / (150 / 60)) * 1000

        sample_rate = 22050
        num_samples = int((estimated_duration_ms / 1000.0) * sample_rate)
        silent_audio = b'\x00\x00' * num_samples

        audio = AudioData(
            data=silent_audio,
            sample_rate=sample_rate,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=estimated_duration_ms
        )

        # Emit complete event
        if observer:
            observer.emit(
                EventType.TTS_COMPLETE,
                {
                    "audio_size_kb": audio.size_kb,
                    "audio_duration_ms": estimated_duration_ms,
                    "latency_ms": self.simulate_latency_ms,
                    "mock": True
                }
            )

        return audio

    def reset(self) -> None:
        """Reset call tracking"""
        self.call_count = 0
        self.spoken_texts.clear()

    def get_last_spoken(self) -> Optional[str]:
        """Get the last text that was spoken"""
        return self.spoken_texts[-1] if self.spoken_texts else None

    def get_all_spoken(self) -> list[str]:
        """Get all texts that were spoken"""
        return self.spoken_texts.copy()
