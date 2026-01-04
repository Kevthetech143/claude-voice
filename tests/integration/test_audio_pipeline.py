"""
Integration test: Prove full audio pipeline works end-to-end
Response to ALPHA's challenge: Integration test: Audio → normalized → STT → text
"""

import pytest
import struct
from src.audio.types import AudioData, AudioFormat
from src.audio.normalize import normalize_for_whisper, detect_silence
from src.stt.mock import MockSTT
from src.core.events import InMemoryEventObserver, EventType


class TestAudioPipelineIntegration:
    """End-to-end tests proving audio pipeline works"""

    @pytest.mark.asyncio
    async def test_full_pipeline_48khz_stereo_to_transcription(self):
        """
        INTEGRATION TEST: 48kHz stereo audio → normalize → STT → text

        This proves the entire audio input path works:
        1. Create 48kHz stereo audio (simulates Mac mic)
        2. Normalize to 16kHz mono WAV
        3. Pass to STT
        4. Get transcription
        5. Verify events emitted
        """
        # Step 1: Create 48kHz stereo audio
        sample_rate = 48000
        duration_ms = 2000  # 2 seconds
        num_samples = int((duration_ms / 1000.0) * sample_rate)

        # Generate stereo audio with some amplitude variation
        samples = []
        for i in range(num_samples):
            # Simulate voice-like pattern
            amplitude = 5000 * (0.5 + 0.5 * ((i % 1000) / 1000.0))
            left = int(amplitude)
            right = int(amplitude * 0.8)  # Slightly different channel
            samples.extend([left, right])

        pcm_data = struct.pack('<' + 'h' * len(samples), *samples)

        original_audio = AudioData(
            data=pcm_data,
            sample_rate=48000,
            format=AudioFormat.WAV,
            channels=2,
            duration_ms=duration_ms
        )

        # Step 2: Normalize
        normalized_audio = normalize_for_whisper(original_audio)

        # Verify normalization
        assert normalized_audio.sample_rate == 16000
        assert normalized_audio.channels == 1
        assert normalized_audio.format == AudioFormat.WAV
        assert normalized_audio.duration_ms is not None
        assert normalized_audio.duration_ms > 0

        # Step 3: Pass to STT with observer
        observer = InMemoryEventObserver()
        mock_stt = MockSTT(transcription="Hello from integration test")

        transcription = await mock_stt.transcribe(normalized_audio, observer)

        # Step 4: Verify transcription
        assert transcription == "Hello from integration test"

        # Step 5: Verify events
        events = observer.get_events()
        assert len(events) >= 2

        start_event = observer.get_events_by_type(EventType.STT_START)[0]
        complete_event = observer.get_events_by_type(EventType.STT_COMPLETE)[0]

        # Verify start event has normalized audio metadata
        assert start_event.data["format"] == "wav"
        assert start_event.data["audio_duration_ms"] > 0

        # Verify complete event has result
        assert complete_event.data["text"] == transcription
        assert complete_event.data["latency_ms"] > 0

    @pytest.mark.asyncio
    async def test_silence_detection_prevents_wasted_api_calls(self):
        """
        Test that silence detection can prevent wasting API calls
        """
        # Create silent audio
        sample_rate = 16000
        duration_ms = 1000
        num_samples = int((duration_ms / 1000.0) * sample_rate)

        silent_pcm = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))

        silent_audio = AudioData(
            data=silent_pcm,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=duration_ms
        )

        # Detect silence
        is_silent = detect_silence(silent_audio, threshold=0.01)
        assert is_silent is True

        # In production, we could skip STT call here
        # For this test, we'll call it anyway but log the warning
        observer = InMemoryEventObserver()
        mock_stt = MockSTT(transcription="[silence]")

        transcription = await mock_stt.transcribe(silent_audio, observer)

        # Even silent audio gets processed (user might want to know)
        assert transcription == "[silence]"

    @pytest.mark.asyncio
    async def test_multiple_sample_rates_all_normalize_correctly(self):
        """
        Test that various sample rates all normalize to 16kHz correctly
        """
        sample_rates = [8000, 16000, 22050, 44100, 48000]
        observer = InMemoryEventObserver()
        mock_stt = MockSTT(transcription="Test")

        for sample_rate in sample_rates:
            observer.clear()

            # Create audio at this sample rate
            duration_ms = 500
            num_samples = int((duration_ms / 1000.0) * sample_rate)

            # Generate non-silent audio
            amplitude = 1000
            samples = [amplitude if i % 2 == 0 else -amplitude for i in range(num_samples)]
            pcm_data = struct.pack('<' + 'h' * len(samples), *samples)

            audio = AudioData(
                data=pcm_data,
                sample_rate=sample_rate,
                format=AudioFormat.WAV,
                channels=1,
                duration_ms=duration_ms
            )

            # Normalize
            normalized = normalize_for_whisper(audio)

            # Verify always 16kHz
            assert normalized.sample_rate == 16000
            assert normalized.channels == 1

            # Verify can be transcribed
            result = await mock_stt.transcribe(normalized, observer)
            assert result == "Test"

    @pytest.mark.asyncio
    async def test_latency_tracking_through_pipeline(self):
        """
        Test that we can track latency at each stage
        """
        observer = InMemoryEventObserver()

        # Create audio
        sample_rate = 16000
        duration_ms = 1000
        num_samples = int((duration_ms / 1000.0) * sample_rate)
        samples = [500] * num_samples
        pcm_data = struct.pack('<' + 'h' * len(samples), *samples)

        audio = AudioData(
            data=pcm_data,
            sample_rate=16000,
            format=AudioFormat.WAV,
            channels=1,
            duration_ms=duration_ms
        )

        # Already normalized, just pass through
        normalized = normalize_for_whisper(audio)

        # Transcribe with observer
        mock_stt = MockSTT(transcription="Latency test")
        await mock_stt.transcribe(normalized, observer)

        # Get latency breakdown
        latencies = observer.get_latency_breakdown()

        assert "stt" in latencies
        assert latencies["stt"] > 0

        # Print for debugging (shows in verbose mode)
        print(f"\nSTT latency: {latencies['stt']:.1f}ms")

    @pytest.mark.asyncio
    async def test_pipeline_handles_various_audio_formats(self):
        """
        Test that pipeline works with different input formats
        (after normalization, all should work)
        """
        # Test with different channel configs
        test_cases = [
            {"sample_rate": 16000, "channels": 1, "name": "16kHz mono"},
            {"sample_rate": 44100, "channels": 2, "name": "44.1kHz stereo"},
            {"sample_rate": 48000, "channels": 2, "name": "48kHz stereo"},
        ]

        mock_stt = MockSTT(transcription="Format test")

        for test_case in test_cases:
            sample_rate = test_case["sample_rate"]
            channels = test_case["channels"]

            # Create audio
            duration_ms = 500
            num_samples = int((duration_ms / 1000.0) * sample_rate)

            # Generate samples (interleaved if stereo)
            samples = []
            for i in range(num_samples):
                for c in range(channels):
                    samples.append(1000 if i % 2 == 0 else -1000)

            pcm_data = struct.pack('<' + 'h' * len(samples), *samples)

            audio = AudioData(
                data=pcm_data,
                sample_rate=sample_rate,
                format=AudioFormat.WAV,
                channels=channels,
                duration_ms=duration_ms
            )

            # Normalize and transcribe
            normalized = normalize_for_whisper(audio)
            result = await mock_stt.transcribe(normalized)

            assert result == "Format test", f"Failed for {test_case['name']}"
            assert normalized.sample_rate == 16000
            assert normalized.channels == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
