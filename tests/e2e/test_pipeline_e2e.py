"""
End-to-end pipeline tests
These tests can be run by AI without any voice/microphone hardware
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.events import InMemoryEventObserver, EventType
from src.core.pipeline import VoicePipeline
from src.llm.mock import MockLLM, ConfigurableMockLLM
from src.llm.chunker import SentenceChunker
from test_harness.runner import TestRunner
from test_harness.scenarios import create_standard_scenarios


# Mock STT for testing
class MockSTT:
    """Mock STT that returns predefined transcripts"""

    def __init__(self, transcript: str = "Hello Claude"):
        self.transcript = transcript

    async def transcribe(self, audio_data) -> str:
        """Return predefined transcript"""
        await asyncio.sleep(0.01)  # Simulate processing
        return self.transcript


# Mock TTS for testing
class MockTTS:
    """Mock TTS that logs instead of speaking"""

    def __init__(self, observer=None):
        self.observer = observer
        self.spoken_texts = []

    async def speak(self, text: str) -> None:
        """Log text instead of speaking"""
        if self.observer:
            self.observer.emit(EventType.TTS_START, {"text": text, "length": len(text)})

        self.spoken_texts.append(text)

        # Simulate TTS latency
        await asyncio.sleep(0.02)

        if self.observer:
            self.observer.emit(EventType.TTS_COMPLETE, {"text": text})


@pytest.mark.asyncio
async def test_basic_pipeline():
    """Test basic pipeline with mocks"""
    observer = InMemoryEventObserver()

    # Create pipeline with mocks
    pipeline = VoicePipeline(
        stt_provider=MockSTT("Hello"),
        llm_provider=MockLLM("Hello! How can I help you?", observer=observer),
        tts_provider=MockTTS(observer=observer),
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    # Process text
    await pipeline.process_text("Hello")

    # Verify events
    events = observer.get_events()
    assert len(events) > 0

    # Check event types
    event_types = [e.event_type for e in events]
    assert EventType.PIPELINE_START in event_types
    assert EventType.LLM_QUERY_START in event_types
    assert EventType.SENTENCE_READY in event_types
    assert EventType.TTS_START in event_types
    assert EventType.PIPELINE_COMPLETE in event_types

    # Check latency
    latencies = observer.get_latency_breakdown()
    assert "pipeline_total" in latencies
    assert latencies["pipeline_total"] < 1000  # Should be fast with mocks

    print(f"\n✓ Basic pipeline test passed")
    print(f"  Events: {len(events)}")
    print(f"  Total latency: {latencies.get('pipeline_total', 0):.1f}ms")


@pytest.mark.asyncio
async def test_sentence_chunking():
    """Test that multi-sentence responses are chunked correctly"""
    observer = InMemoryEventObserver()
    tts = MockTTS(observer=observer)

    response = "Hello! How are you today? I'm here to help."

    pipeline = VoicePipeline(
        stt_provider=MockSTT(),
        llm_provider=MockLLM(response, observer=observer),
        tts_provider=tts,
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    await pipeline.process_text("Hello")

    # Check that we got multiple TTS calls (one per sentence)
    sentence_events = observer.get_events_by_type(EventType.SENTENCE_READY)
    assert len(sentence_events) == 3  # Three sentences

    # Check that TTS received each sentence
    assert len(tts.spoken_texts) == 3

    print(f"\n✓ Sentence chunking test passed")
    print(f"  Sentences detected: {len(sentence_events)}")
    for i, text in enumerate(tts.spoken_texts, 1):
        print(f"  Sentence {i}: {text}")


@pytest.mark.asyncio
async def test_with_test_runner():
    """Test using the test harness (AI-driven testing)"""
    observer = InMemoryEventObserver()
    tts = MockTTS(observer=observer)

    # Create configurable mock for realistic responses
    llm = ConfigurableMockLLM(
        responses={
            "hello": "Hello! I'm Claude. How can I help you today?",
            "2 plus 2": "Two plus two equals four.",
            "yourself": "I'm Claude, an AI assistant created by Anthropic. I'm here to help answer questions and have conversations.",
        },
        default_response="I'm not sure about that.",
        observer=observer,
    )

    pipeline = VoicePipeline(
        stt_provider=MockSTT(),
        llm_provider=llm,
        tts_provider=tts,
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    # Run standard scenarios
    runner = TestRunner()
    scenarios = create_standard_scenarios()

    results = await runner.run_multiple_scenarios(pipeline, scenarios)

    # Print results
    runner.print_summary()

    # Assert all passed
    assert runner.all_passed(), "Some scenarios failed"

    print(f"\n✓ Test harness validation passed")
    print(f"  Scenarios run: {len(results)}")
    print(f"  All tests passed: {runner.all_passed()}")


@pytest.mark.asyncio
async def test_latency_requirement():
    """Test that pipeline meets latency requirements"""
    observer = InMemoryEventObserver()

    pipeline = VoicePipeline(
        stt_provider=MockSTT(),
        llm_provider=MockLLM("Quick response.", observer=observer, token_delay_ms=1),
        tts_provider=MockTTS(observer=observer),
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    await pipeline.process_text("Hi")

    latencies = observer.get_latency_breakdown()
    total_latency = latencies.get("pipeline_total", 0)

    # With mocks, should be very fast (<100ms)
    assert total_latency < 100, f"Latency too high: {total_latency:.1f}ms"

    print(f"\n✓ Latency requirement test passed")
    print(f"  Total latency: {total_latency:.1f}ms")


if __name__ == "__main__":
    # Run tests directly
    print("=" * 60)
    print("RUNNING END-TO-END PIPELINE TESTS")
    print("=" * 60)

    asyncio.run(test_basic_pipeline())
    asyncio.run(test_sentence_chunking())
    asyncio.run(test_with_test_runner())
    asyncio.run(test_latency_requirement())

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
