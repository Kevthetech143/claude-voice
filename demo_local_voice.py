#!/usr/bin/env python3
"""
Demo: Fully Local Voice Assistant
Uses whisper.cpp + Piper TTS for offline operation
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.providers import ProviderConfig, ProviderFactory
from src.core.models import ModelManager
from src.core.pipeline import VoicePipeline
from src.core.events import InMemoryEventObserver
from src.llm.claude_api import ClaudeAPI
from src.llm.chunker_fixed import SentenceChunker


async def main():
    """Run local voice assistant demo"""
    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Local Demo")
    print("=" * 70)

    # 1. Setup model manager
    print("\n📦 Checking local models...")
    manager = ModelManager()
    cached = manager.list_cached_models()

    if not cached['whisper'] or not cached['piper']:
        print("\n⚠️  Local models not found!")
        print("   Please run: python setup_local_voice.py")
        print("\n   This will download:")
        print("   • Whisper model (~466MB for 'small')")
        print("   • Piper voice (~63MB)")
        sys.exit(1)

    cache_size = manager.get_cache_size_mb()
    print(f"   ✅ Models cached ({cache_size:.1f}MB)")
    print(f"   • Whisper: {', '.join(cached['whisper'])}")
    print(f"   • Piper: {', '.join(cached['piper'])}")

    # 2. Configure for local-only operation
    print("\n🔧 Configuring local-only providers...")
    config = ProviderConfig.local_only()
    print(f"   • STT: {config.stt_provider.value}")
    print(f"   • TTS: {config.tts_provider.value}")
    print(f"   • Whisper Model: {config.whisper_model}")
    print(f"   • Piper Voice: {config.piper_voice}")

    # 3. Create providers
    print("\n🎤 Initializing voice pipeline...")
    observer = InMemoryEventObserver()

    try:
        stt_provider = ProviderFactory.create_stt_provider(config, observer)
        tts_provider = ProviderFactory.create_tts_provider(config, observer)
        print("   ✅ Local STT/TTS providers ready")
    except Exception as e:
        print(f"\n❌ Error creating providers: {e}")
        print("\n   This likely means:")
        print("   • whisper.cpp not installed (BETA building this)")
        print("   • Piper TTS not installed (BETA building this)")
        print("\n   Falling back to mock providers for now...")

        # Temporary: Use mocks until BETA delivers
        from src.stt.mock import MockSTT
        from src.tts.mock import MockTTS
        stt_provider = MockSTT(transcription="Hello Claude, what can you do?")
        tts_provider = MockTTS()

    # LLM and chunker
    llm_provider = ClaudeAPI(
        api_key=config.whisper_api_key or "demo-key",
        system_message="You are Claude, a helpful voice assistant. Keep responses concise for voice interaction."
    )
    chunker = SentenceChunker()

    # Create pipeline
    pipeline = VoicePipeline(
        stt_provider=stt_provider,
        llm_provider=llm_provider,
        tts_provider=tts_provider,
        chunker=chunker,
        observer=observer
    )

    print("   ✅ Pipeline ready")

    # 4. Demo scenarios
    print("\n" + "=" * 70)
    print("DEMO: Local Voice Interaction")
    print("=" * 70)

    print("\n💬 Scenario: User asks 'What can you do?'")
    print("   [Simulating local Whisper transcription...]")

    await pipeline.process_text("What can you do?")

    events = observer.get_events()
    print(f"\n📊 Pipeline Statistics:")
    print(f"   • Total Events: {len(events)}")
    print(f"   • STT Events: {sum(1 for e in events if 'stt' in e.event_type.value)}")
    print(f"   • LLM Events: {sum(1 for e in events if 'llm' in e.event_type.value)}")
    print(f"   • TTS Events: {sum(1 for e in events if 'tts' in e.event_type.value)}")
    print(f"   • Sentences Spoken: {sum(1 for e in events if e.event_type.value == 'sentence_ready')}")

    # Calculate latency
    if events:
        start_time = events[0].timestamp
        end_time = events[-1].timestamp
        latency_ms = (end_time - start_time) * 1000
        print(f"   • Total Latency: {latency_ms:.0f}ms")

    print("\n" + "=" * 70)
    print("✅ Demo Complete!")
    print("=" * 70)

    print("\n🎯 Benefits of Local Operation:")
    print("   • Zero API costs (except Claude LLM)")
    print("   • Works offline (STT/TTS)")
    print("   • Privacy: audio stays on device")
    print("   • Fast: no network round-trips for STT/TTS")
    print("   • Reliable: no rate limits or API outages")

    print(f"\n📁 Models cached at: {manager.cache_dir}")
    print(f"   Total size: {cache_size:.1f}MB")

    print("\n🚀 Next Steps:")
    print("   • Wait for BETA to complete LocalWhisperSTT")
    print("   • Wait for BETA to complete LocalPiperTTS")
    print("   • Test with real audio input/output")
    print("   • Benchmark vs cloud APIs")
    print("   • Update project hive with learnings")


if __name__ == "__main__":
    asyncio.run(main())
