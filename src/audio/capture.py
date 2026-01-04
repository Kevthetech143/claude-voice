"""
Audio capture from microphone
Provides mockable interface for AI testing
"""

import asyncio
from typing import Protocol, Optional
from .types import AudioData, AudioFormat


class AudioCapturer(Protocol):
    """Protocol for audio capture implementations"""

    async def capture(self, duration_ms: int) -> AudioData:
        """
        Capture audio from input device

        Args:
            duration_ms: Duration to record in milliseconds

        Returns:
            AudioData containing recorded audio
        """
        ...

    async def start_stream(self) -> None:
        """Start continuous audio stream"""
        ...

    async def stop_stream(self) -> AudioData:
        """Stop stream and return captured audio"""
        ...


class MockAudioCapturer:
    """
    Mock audio capturer for testing
    Returns predefined audio data without requiring hardware
    """

    def __init__(self, mock_data: Optional[bytes] = None):
        """
        Initialize mock capturer

        Args:
            mock_data: Optional predefined audio data to return
                      If None, generates silent audio
        """
        self.mock_data = mock_data
        self._streaming = False
        self._stream_buffer: list[bytes] = []

    async def capture(self, duration_ms: int) -> AudioData:
        """
        Mock capture - returns silent audio or predefined data

        Args:
            duration_ms: Duration to simulate

        Returns:
            AudioData with mock content
        """
        # Simulate capture delay
        await asyncio.sleep(duration_ms / 1000.0)

        if self.mock_data:
            data = self.mock_data
        else:
            # Generate silent audio (16-bit PCM, 16kHz mono)
            sample_rate = 16000
            bytes_per_sample = 2  # 16-bit
            num_samples = int((duration_ms / 1000.0) * sample_rate)
            data = b'\x00\x00' * num_samples

        return AudioData(
            data=data,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=duration_ms
        )

    async def start_stream(self) -> None:
        """Start mock streaming"""
        self._streaming = True
        self._stream_buffer.clear()

    async def stop_stream(self) -> AudioData:
        """Stop mock streaming and return captured data"""
        self._streaming = False

        # Return mock data or silent audio
        if self.mock_data:
            data = self.mock_data
            duration_ms = 1000.0  # Assume 1 second
        else:
            # 1 second of silence
            sample_rate = 16000
            num_samples = sample_rate
            data = b'\x00\x00' * num_samples
            duration_ms = 1000.0

        return AudioData(
            data=data,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=duration_ms
        )


# TODO: Real microphone implementation using pyaudio or sounddevice
# This will be implemented when we need actual voice input
# For now, MockAudioCapturer is sufficient for testing
