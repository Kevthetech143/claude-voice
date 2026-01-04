#!/usr/bin/env python3
"""
Demo script to show AI can test the entire pipeline
Run this to validate the voice assistant without any voice hardware
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.events import InMemoryEventObserver, EventType
from src.core.pipeline import VoicePipeline
from src.llm.mock import MockLLM, ConfigurableMockLLM
from src.llm.chunker import SentenceChunker
from test_harness.runner import TestRunner
from test_harness.scenarios import create_standard_scenarios


# Mock providers (BETA will replace with real ones)
class MockSTT:
    async def transcribe(self, audio_data) -> str:
        await asyncio.sleep(0.01)
        return "Hello Claude"


class MockTTS:
    def __init__(self, observer=None):
        self.observer = observer
        self.spoken_texts = []

    async def speak(self, text: str) -> None:
        if self.observer:
            self.observer.emit(EventType.TTS_START, {"text": text, "length": len(text)})

        self.spoken_texts.append(text)
        print(f"  🔊 TTS: {text}")

        await asyncio.sleep(0.02)

        if self.observer:
            self.observer.emit(EventType.TTS_COMPLETE, {"text": text})


async def demo_basic_interaction():
    """Demo 1: Basic interaction"""
    print("\n" + "=" * 60)
    print("DEMO 1: Basic Voice Interaction (Simulated)")
    print("=" * 60)

    observer = InMemoryEventObserver()
    tts = MockTTS(observer=observer)

    pipeline = VoicePipeline(
        stt_provider=MockSTT(),
        llm_provider=MockLLM(
            "Hello! I'm Claude, your voice assistant. How can I help you today?",
            observer=observer,
        ),
        tts_provider=tts,
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    print("\n👤 User: Hello Claude")
    await pipeline.process_text("Hello Claude")

    print(f"\n📊 Pipeline completed")
    observer.print_summary()


async def demo_sentence_chunking():
    """Demo 2: Sentence chunking"""
    print("\n" + "=" * 60)
    print("DEMO 2: Sentence Chunking (Parallel TTS)")
    print("=" * 60)

    observer = InMemoryEventObserver()
    tts = MockTTS(observer=observer)

    response = (
        "Streaming is a key optimization for voice assistants. "
        "It allows us to start speaking before the LLM finishes generating. "
        "This dramatically reduces perceived latency. "
        "The user hears the first sentence in under a second!"
    )

    pipeline = VoicePipeline(
        stt_provider=MockSTT(),
        llm_provider=MockLLM(response, observer=observer, token_delay_ms=5),
        tts_provider=tts,
        chunker=SentenceChunker(observer=observer),
        observer=observer,
    )

    print("\n👤 User: Explain how streaming works")
    await pipeline.process_text("Explain how streaming works")

    print(f"\n📊 Detected {len(tts.spoken_texts)} sentences")
    print("✓ Each sentence was sent to TTS immediately (parallel processing)")

    observer.print_summary()


async def demo_test_harness():
    """Demo 3: AI-driven test harness"""
    print("\n" + "=" * 60)
    print("DEMO 3: AI-Driven Test Harness")
    print("=" * 60)

    observer = InMemoryEventObserver()
    tts = MockTTS(observer=observer)

    llm = ConfigurableMockLLM(
        responses={
            "hello": "Hello! I'm Claude. How can I help you today?",
            "2 plus 2": "Two plus two equals 4.",
            "yourself": "I'm Claude, an AI assistant. I help with questions and conversations.",
            "streaming": "Streaming allows me to respond faster by speaking while still thinking.",
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

    runner = TestRunner()
    scenarios = create_standard_scenarios()

    print(f"\n🤖 AI is running {len(scenarios)} test scenarios...\n")

    results = await runner.run_multiple_scenarios(pipeline, scenarios)

    runner.print_summary()

    if runner.all_passed():
        print("\n✅ AI has verified the pipeline works correctly!")
    else:
        print("\n❌ AI found issues that need fixing")
        sys.exit(1)


async def main():
    """Run all demos"""
    print("\n" + "=" * 70)
    print("CLAUDE VOICE ASSISTANT - AI-TESTABLE PIPELINE DEMO")
    print("=" * 70)
    print("\nThis demonstrates that AI can test the entire voice pipeline")
    print("without any voice hardware, microphone, or speakers.")
    print("\nKey innovations:")
    print("  ✓ Observable pipeline (event logging)")
    print("  ✓ Mock providers (test without APIs)")
    print("  ✓ Sentence chunking (parallel TTS)")
    print("  ✓ Test harness (AI-driven validation)")
    print("=" * 70)

    await demo_basic_interaction()
    await demo_sentence_chunking()
    await demo_test_harness()

    print("\n" + "=" * 70)
    print("🎉 ALL DEMOS COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. BETA builds real audio pipeline (STT, TTS)")
    print("  2. Integration: Replace mocks with real providers")
    print("  3. End-to-end test with voice I/O")
    print("  4. Production deployment")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
