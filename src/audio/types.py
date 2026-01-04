"""
Audio data types and formats
Provides standard representations for audio throughout the pipeline
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AudioFormat(str, Enum):
    """Supported audio formats"""
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"
    AIFF = "aiff"
    PCM = "pcm"  # Raw PCM data


@dataclass
class AudioData:
    """
    Container for audio data with metadata

    Provides a standard format for audio throughout the pipeline:
    - STT receives AudioData
    - TTS produces AudioData
    - All components work with this common format

    Attributes:
        data: Raw audio bytes
        sample_rate: Sample rate in Hz (e.g., 16000, 44100)
        format: Audio format (WAV, MP3, etc.)
        channels: Number of audio channels (1=mono, 2=stereo)
        duration_ms: Duration in milliseconds (optional, calculated if not provided)
    """
    data: bytes
    sample_rate: int
    format: AudioFormat
    channels: int = 1
    duration_ms: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate audio data parameters"""
        if self.sample_rate <= 0:
            raise ValueError(f"Invalid sample_rate: {self.sample_rate}")
        if self.channels <= 0:
            raise ValueError(f"Invalid channels: {self.channels}")
        if not self.data:
            raise ValueError("Audio data cannot be empty")

    @property
    def size_bytes(self) -> int:
        """Get size of audio data in bytes"""
        return len(self.data)

    @property
    def size_kb(self) -> float:
        """Get size of audio data in kilobytes"""
        return self.size_bytes / 1024

    def calculate_duration_ms(self, bits_per_sample: int = 16) -> float:
        """
        Calculate duration in milliseconds

        Args:
            bits_per_sample: Bits per sample (typically 16)

        Returns:
            Duration in milliseconds
        """
        bytes_per_sample = bits_per_sample / 8
        num_samples = self.size_bytes / (bytes_per_sample * self.channels)
        duration_seconds = num_samples / self.sample_rate
        return duration_seconds * 1000

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (excludes raw data)"""
        return {
            "sample_rate": self.sample_rate,
            "format": self.format.value,
            "channels": self.channels,
            "duration_ms": self.duration_ms,
            "size_bytes": self.size_bytes,
        }


def create_whisper_compatible_audio(data: bytes) -> AudioData:
    """
    Create AudioData configured for Whisper API

    Whisper expects:
    - 16kHz sample rate
    - Mono (1 channel)
    - WAV or FLAC format

    Args:
        data: Raw audio bytes (should already be converted to 16kHz mono)

    Returns:
        AudioData configured for Whisper
    """
    return AudioData(
        data=data,
        sample_rate=16000,
        format=AudioFormat.WAV,
        channels=1
    )
