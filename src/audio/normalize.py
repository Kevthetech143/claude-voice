"""
Audio normalization and format conversion
Handles resampling, mono conversion, and format standardization
"""

import io
import wave
import struct
from typing import Optional
from .types import AudioData, AudioFormat
from .exceptions import (
    AudioNormalizationError,
    AudioFormatError,
    AudioTooShortError,
    AudioTooLongError
)


# Constants for Whisper API limits
WHISPER_SAMPLE_RATE = 16000
WHISPER_CHANNELS = 1
WHISPER_MAX_FILE_SIZE_MB = 25.0
WHISPER_MIN_DURATION_MS = 100.0  # 100ms minimum


def validate_audio_for_whisper(audio: AudioData) -> None:
    """
    Validate audio meets Whisper API requirements

    Args:
        audio: Audio data to validate

    Raises:
        AudioTooShortError: If audio is too short
        AudioTooLongError: If audio exceeds size limit
        AudioFormatError: If format is unsupported
    """
    # Check duration
    if audio.duration_ms and audio.duration_ms < WHISPER_MIN_DURATION_MS:
        raise AudioTooShortError(audio.duration_ms, WHISPER_MIN_DURATION_MS)

    # Check file size
    size_mb = audio.size_bytes / (1024 * 1024)
    if size_mb > WHISPER_MAX_FILE_SIZE_MB:
        raise AudioTooLongError(size_mb, WHISPER_MAX_FILE_SIZE_MB)

    # Check format
    if audio.format not in [AudioFormat.WAV, AudioFormat.FLAC, AudioFormat.MP3]:
        raise AudioFormatError(
            f"Whisper requires WAV/FLAC/MP3, got {audio.format.value}"
        )


def normalize_for_whisper(
    audio: AudioData,
    bits_per_sample: int = 16
) -> AudioData:
    """
    Normalize audio to Whisper API requirements

    Converts any audio to:
    - 16kHz sample rate
    - Mono (1 channel)
    - WAV format
    - PCM 16-bit encoding

    Args:
        audio: Input audio (any sample rate, channels, format)
        bits_per_sample: Bits per sample for input (default 16)

    Returns:
        Normalized AudioData ready for Whisper

    Raises:
        AudioNormalizationError: If normalization fails
    """
    try:
        # If already normalized, validate and return
        if (audio.sample_rate == WHISPER_SAMPLE_RATE and
            audio.channels == WHISPER_CHANNELS and
            audio.format == AudioFormat.WAV):
            validate_audio_for_whisper(audio)
            return audio

        # Parse input audio
        samples = _parse_audio_to_samples(audio, bits_per_sample)

        # Convert stereo to mono if needed
        if audio.channels > 1:
            samples = _convert_to_mono(samples, audio.channels)

        # Resample if needed
        if audio.sample_rate != WHISPER_SAMPLE_RATE:
            samples = _resample(
                samples,
                audio.sample_rate,
                WHISPER_SAMPLE_RATE
            )

        # Convert samples back to WAV bytes
        wav_data = _samples_to_wav(samples, WHISPER_SAMPLE_RATE)

        # Create normalized audio
        duration_ms = (len(samples) / WHISPER_SAMPLE_RATE) * 1000
        normalized = AudioData(
            data=wav_data,
            sample_rate=WHISPER_SAMPLE_RATE,
            format=AudioFormat.WAV,
            channels=WHISPER_CHANNELS,
            duration_ms=duration_ms
        )

        # Validate meets Whisper requirements
        validate_audio_for_whisper(normalized)

        return normalized

    except (AudioTooShortError, AudioTooLongError, AudioFormatError):
        # Re-raise validation errors as-is
        raise
    except Exception as e:
        raise AudioNormalizationError(f"Failed to normalize audio: {e}") from e


def _parse_audio_to_samples(
    audio: AudioData,
    bits_per_sample: int
) -> list[float]:
    """
    Parse audio data to normalized float samples [-1.0, 1.0]

    Args:
        audio: Input audio
        bits_per_sample: Bits per sample

    Returns:
        List of normalized samples
    """
    if audio.format == AudioFormat.WAV:
        return _parse_wav_samples(audio.data, bits_per_sample)
    else:
        # For non-WAV formats, assume raw PCM for now
        # In production, use library like pydub for format conversion
        return _parse_pcm_samples(audio.data, bits_per_sample)


def _parse_wav_samples(wav_data: bytes, bits_per_sample: int) -> list[float]:
    """Parse WAV file to samples"""
    try:
        with wave.open(io.BytesIO(wav_data), 'rb') as wav_file:
            num_frames = wav_file.getnframes()
            raw_data = wav_file.readframes(num_frames)
            return _parse_pcm_samples(raw_data, bits_per_sample)
    except Exception as e:
        raise AudioFormatError(f"Failed to parse WAV data: {e}") from e


def _parse_pcm_samples(pcm_data: bytes, bits_per_sample: int) -> list[float]:
    """
    Parse raw PCM data to normalized samples

    Args:
        pcm_data: Raw PCM bytes
        bits_per_sample: 8, 16, 24, or 32

    Returns:
        Normalized samples [-1.0, 1.0]
    """
    if bits_per_sample == 16:
        # 16-bit signed PCM
        samples = struct.unpack('<' + 'h' * (len(pcm_data) // 2), pcm_data)
        return [s / 32768.0 for s in samples]
    elif bits_per_sample == 8:
        # 8-bit unsigned PCM
        samples = struct.unpack('B' * len(pcm_data), pcm_data)
        return [(s - 128) / 128.0 for s in samples]
    else:
        raise AudioFormatError(f"Unsupported bits_per_sample: {bits_per_sample}")


def _convert_to_mono(samples: list[float], channels: int) -> list[float]:
    """
    Convert multi-channel audio to mono by averaging

    Args:
        samples: Interleaved samples
        channels: Number of channels

    Returns:
        Mono samples
    """
    mono = []
    for i in range(0, len(samples), channels):
        # Average all channels for this frame
        frame_samples = samples[i:i+channels]
        mono.append(sum(frame_samples) / len(frame_samples))
    return mono


def _resample(
    samples: list[float],
    from_rate: int,
    to_rate: int
) -> list[float]:
    """
    Resample audio using linear interpolation

    Note: This is a simple implementation. For production,
    consider using a library like `samplerate` or `librosa`
    for higher quality resampling.

    Args:
        samples: Input samples
        from_rate: Source sample rate
        to_rate: Target sample rate

    Returns:
        Resampled audio
    """
    if from_rate == to_rate:
        return samples

    # Calculate ratio
    ratio = to_rate / from_rate
    new_length = int(len(samples) * ratio)

    # Linear interpolation
    resampled = []
    for i in range(new_length):
        # Map new index to old index
        old_index = i / ratio
        index_floor = int(old_index)
        index_ceil = min(index_floor + 1, len(samples) - 1)

        # Interpolate
        if index_floor == index_ceil:
            resampled.append(samples[index_floor])
        else:
            fraction = old_index - index_floor
            value = (
                samples[index_floor] * (1 - fraction) +
                samples[index_ceil] * fraction
            )
            resampled.append(value)

    return resampled


def _samples_to_wav(samples: list[float], sample_rate: int) -> bytes:
    """
    Convert normalized samples to WAV bytes

    Args:
        samples: Normalized samples [-1.0, 1.0]
        sample_rate: Sample rate

    Returns:
        WAV file bytes
    """
    # Convert to 16-bit PCM
    pcm_samples = [int(max(-1.0, min(1.0, s)) * 32767) for s in samples]
    pcm_data = struct.pack('<' + 'h' * len(pcm_samples), *pcm_samples)

    # Create WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    return wav_buffer.getvalue()


def detect_silence(audio: AudioData, threshold: float = 0.01) -> bool:
    """
    Detect if audio is mostly silent

    Args:
        audio: Audio data to check
        threshold: RMS threshold for silence (default 0.01)

    Returns:
        True if audio is silent
    """
    try:
        samples = _parse_audio_to_samples(audio, 16)

        # Calculate RMS (root mean square)
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5

        return rms < threshold

    except Exception:
        # If we can't parse, assume not silent
        return False
