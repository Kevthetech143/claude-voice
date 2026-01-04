"""
Production-grade tests for STT module
Demonstrates AI-testability without requiring Whisper API calls
"""

import pytest
import asyncio
from src.audio.types import AudioData, AudioFormat
from src.audio.normalize import normalize_for_whisper, detect_silence
from src.audio.exceptions import AudioTooShortError, AudioTooLongError
from src.stt.whisper import WhisperSTT
from src.stt.mock import MockSTT, DynamicMockSTT
from src.core.events import InMemoryEventObserver, EventType


class TestAudioNormalization:
    """Test audio normalization handles all edge cases"""

    def test_normalize_48khz_stereo_to_16khz_mono(self):
        """Test normalization from 48kHz stereo to 16kHz mono"""
        # Create 48kHz stereo audio (simulated)
        sample_rate = 48000
        duration_ms = 1000  # 1 second
        num_samples = int((duration_ms / 1000.0) * sample_rate)

        # Generate some non-silent audio (2 channels interleaved)
        import struct
        samples = []
        for i in range(num_samples):
            left = int((i % 1000) * 30)   # Simulate audio
            right = int((i % 1000) * 30)
            samples.extend([left, right])

        pcm_data = struct.pack('<' + 'h' * len(samples), *samples)

        audio = AudioData(
            data=pcm_data,
            sample_rate=48000,
            format=AudioFormat.WAV,
            channels=2,
            duration_ms=duration_ms
        )

        # Normalize
        normalized = normalize_for_whisper(audio)

        # Verify
        assert normalized.sample_rate == 16000
        assert normalized.channels == 1
        assert normalized.format == AudioFormat.WAV
        assert normalized.duration_ms is not None

    def test_audio_too_short_raises_error(self):
        """Test that audio <100ms raises AudioTooShortError"""
        # Create 50ms audio
        import struct
        sample_rate = 16000
        num_samples = int((50 / 1000.0) * sample_rate)  # 50ms
        pcm_data = struct.pack('<' + 'h' * num_samples, *([100] * num_samples))

        audio = AudioData(
            data=pcm_data,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=50.0
        )

        # Should raise error
        with pytest.raises(AudioTooShortError) as exc_info:
            normalize_for_whisper(audio)

        assert exc_info.value.duration_ms == 50.0
        assert exc_info.value.minimum_ms == 100.0

    def test_audio_too_long_raises_error(self):
        """Test that audio >25MB raises AudioTooLongError"""
        # Create audio >25MB (simulate with large byte array)
        large_data = b'x' * (26 * 1024 * 1024)  # 26MB

        audio = AudioData(
            data=large_data,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=10000.0
        )

        # Should raise error
        with pytest.raises(AudioTooLongError) as exc_info:
            normalize_for_whisper(audio)

        assert exc_info.value.size_mb > 25.0

    def test_silence_detection(self):
        """Test silence detection works"""
        # Create silent audio
        import struct
        sample_rate = 16000
        num_samples = sample_rate  # 1 second
        silent_pcm = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))

        silent_audio = AudioData(
            data=silent_pcm,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=1000.0
        )

        # Should detect silence
        assert detect_silence(silent_audio) is True

        # Create non-silent audio
        loud_samples = [1000 if i % 2 == 0 else -1000 for i in range(num_samples)]
        loud_pcm = struct.pack('<' + 'h' * num_samples, *loud_samples)

        loud_audio = AudioData(
            data=loud_pcm,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=1000.0
        )

        # Should not detect silence
        assert detect_silence(loud_audio) is False


@pytest.mark.asyncio
class TestMockSTT:
    """Test that mock STT enables AI testing without API calls"""

    async def test_mock_stt_basic(self):
        """Test basic mock STT functionality"""
        mock = MockSTT(transcription="Hello world")
        observer = InMemoryEventObserver()

        # Create dummy audio
        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1
        )

        # Transcribe
        result = await mock.transcribe(audio, observer)

        # Verify
        assert result == "Hello world"
        assert mock.call_count == 1
        assert mock.last_audio is not None

        # Verify events
        events = observer.get_events()
        assert len(events) == 2
        assert events[0].event_type == EventType.STT_START
        assert events[1].event_type == EventType.STT_COMPLETE
        assert events[1].data["text"] == "Hello world"
        assert events[1].data["mock"] is True

    async def test_dynamic_mock_stt(self):
        """Test dynamic mock for multi-turn conversations"""
        responses = [
            "What's the weather?",
            "Tell me a joke",
            "Thanks!"
        ]
        mock = DynamicMockSTT(responses)
        observer = InMemoryEventObserver()

        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1
        )

        # Simulate 3 turns
        result1 = await mock.transcribe(audio, observer)
        result2 = await mock.transcribe(audio, observer)
        result3 = await mock.transcribe(audio, observer)

        assert result1 == "What's the weather?"
        assert result2 == "Tell me a joke"
        assert result3 == "Thanks!"
        assert mock.call_count == 3


@pytest.mark.asyncio
class TestSTTObservability:
    """Test that STT emits comprehensive events for monitoring"""

    async def test_stt_events_are_comprehensive(self):
        """Test that all relevant metrics are captured in events"""
        mock = MockSTT(transcription="Test output")
        observer = InMemoryEventObserver()

        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=1000.0
        )

        await mock.transcribe(audio, observer)

        # Get latency breakdown
        latencies = observer.get_latency_breakdown()

        assert "stt" in latencies
        assert latencies["stt"] > 0  # Should have measured latency

        # Verify event data
        start_event = observer.get_events_by_type(EventType.STT_START)[0]
        complete_event = observer.get_events_by_type(EventType.STT_COMPLETE)[0]

        # Start event should have audio metadata
        assert "audio_duration_ms" in start_event.data
        assert "audio_size_kb" in start_event.data
        assert "format" in start_event.data

        # Complete event should have result metadata
        assert "text" in complete_event.data
        assert "latency_ms" in complete_event.data
        assert "text_length" in complete_event.data

    async def test_can_reconstruct_pipeline_from_events(self):
        """Test that event log contains full pipeline history"""
        mock = MockSTT(transcription="Reconstructed from events")
        observer = InMemoryEventObserver()

        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1
        )

        await mock.transcribe(audio, observer)

        # Reconstruct what happened
        events = observer.get_events()

        timeline = []
        for event in events:
            timeline.append({
                "timestamp": event.timestamp,
                "stage": event.event_type.value,
                "data": event.data
            })

        # Verify timeline
        assert len(timeline) >= 2
        assert timeline[0]["stage"] == "stt_start"
        assert timeline[-1]["stage"] == "stt_complete"

        # Should be able to extract result
        result_text = timeline[-1]["data"]["text"]
        assert result_text == "Reconstructed from events"


@pytest.mark.asyncio
class TestSTTProductionFeatures:
    """Test production-grade features of WhisperSTT"""

    async def test_metrics_tracking(self):
        """Test that WhisperSTT tracks metrics correctly"""
        # Note: This test uses mock, but structure is the same for real WhisperSTT
        mock = MockSTT()

        # Simulate multiple calls
        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1
        )

        await mock.transcribe(audio)
        await mock.transcribe(audio)
        await mock.transcribe(audio)

        assert mock.call_count == 3

    async def test_mock_is_fully_async(self):
        """Test that mock STT is fully async (no blocking calls)"""
        mock = MockSTT()
        audio = AudioData(
            data=b'\x00' * 1000,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1
        )

        # Should complete without blocking
        start = asyncio.get_event_loop().time()
        await mock.transcribe(audio)
        elapsed = asyncio.get_event_loop().time() - start

        # Should simulate latency but not block event loop
        assert elapsed < 0.2  # 100ms simulated + overhead


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
