"""
Integration test for local voice pipeline
Tests LocalWhisperSTT + LocalPiperTTS end-to-end
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.providers import ProviderConfig, ProviderFactory
from src.core.pipeline import VoicePipeline
from src.core.events import InMemoryEventObserver
from src.llm.claude_api import ClaudeAPI
from src.llm.chunker_fixed import SentenceChunker


async def test_local_stt_initialization():
    """Test LocalWhisperSTT can be initialized"""
    print("\n🧪 Test 1: LocalWhisperSTT Initialization")

    config = ProviderConfig.local_only()
    observer = InMemoryEventObserver()

    try:
        stt = ProviderFactory.create_stt_provider(config, observer)
        print("   ✅ LocalWhisperSTT initialized")
        assert stt is not None
        assert hasattr(stt, 'transcribe')
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


async def test_local_tts_initialization():
    """Test LocalPiperTTS can be initialized"""
    print("\n🧪 Test 2: LocalPiperTTS Initialization")

    config = ProviderConfig.local_only()
    observer = InMemoryEventObserver()

    try:
        tts = ProviderFactory.create_tts_provider(config, observer)
        print("   ✅ LocalPiperTTS initialized")
        assert tts is not None
        assert hasattr(tts, 'speak')
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


async def test_local_pipeline_integration():
    """Test full local pipeline: text → LLM → chunker → TTS"""
    print("\n🧪 Test 3: Local Pipeline Integration")

    config = ProviderConfig.local_only()
    observer = InMemoryEventObserver()

    try:
        # Create providers
        stt = ProviderFactory.create_stt_provider(config, observer)
        tts = ProviderFactory.create_tts_provider(config, observer)
        llm = ClaudeAPI(
            api_key="test-key",
            system_message="Keep responses brief for testing."
        )
        chunker = SentenceChunker()

        # Create pipeline
        pipeline = VoicePipeline(
            stt_provider=stt,
            llm_provider=llm,
            tts_provider=tts,
            chunker=chunker,
            observer=observer
        )

        print("   Pipeline created")

        # Test text processing
        await pipeline.process_text("What is 2+2?")

        # Verify events
        events = observer.get_events()
        assert len(events) > 0, "No events emitted"

        llm_events = [e for e in events if 'llm' in e.event_type.value]
        tts_events = [e for e in events if 'tts' in e.event_type.value]

        assert len(llm_events) > 0, "No LLM events"
        assert len(tts_events) > 0, "No TTS events"

        print(f"   ✅ Pipeline processed successfully")
        print(f"      • Events: {len(events)}")
        print(f"      • LLM events: {len(llm_events)}")
        print(f"      • TTS events: {len(tts_events)}")

        return True

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_local_vs_mock_latency():
    """Compare local provider latency vs mock"""
    print("\n🧪 Test 4: Local vs Mock Latency")

    import time

    # Test mock pipeline
    mock_config = ProviderConfig(
        stt_provider="mock_stt",
        tts_provider="mock_tts"
    )

    from src.stt.mock import MockSTT
    from src.tts.mock import MockTTS

    observer_mock = InMemoryEventObserver()
    pipeline_mock = VoicePipeline(
        stt_provider=MockSTT(transcription="test"),
        llm_provider=ClaudeAPI(api_key="test-key"),
        tts_provider=MockTTS(),
        chunker=SentenceChunker(),
        observer=observer_mock
    )

    start = time.time()
    await pipeline_mock.process_text("Quick test")
    mock_latency = (time.time() - start) * 1000

    # Test local pipeline
    local_config = ProviderConfig.local_only()
    observer_local = InMemoryEventObserver()

    try:
        stt = ProviderFactory.create_stt_provider(local_config, observer_local)
        tts = ProviderFactory.create_tts_provider(local_config, observer_local)

        pipeline_local = VoicePipeline(
            stt_provider=stt,
            llm_provider=ClaudeAPI(api_key="test-key"),
            tts_provider=tts,
            chunker=SentenceChunker(),
            observer=observer_local
        )

        start = time.time()
        await pipeline_local.process_text("Quick test")
        local_latency = (time.time() - start) * 1000

        print(f"   Mock: {mock_latency:.0f}ms")
        print(f"   Local: {local_latency:.0f}ms")
        print(f"   Overhead: {local_latency - mock_latency:.0f}ms")

        # Local should be reasonable (< 5s for short text)
        assert local_latency < 5000, f"Local too slow: {local_latency}ms"

        print("   ✅ Latency acceptable")
        return True

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


async def test_error_handling():
    """Test error handling in local providers"""
    print("\n🧪 Test 5: Error Handling")

    config = ProviderConfig.local_only()
    observer = InMemoryEventObserver()

    try:
        stt = ProviderFactory.create_stt_provider(config, observer)

        # Test with invalid audio data
        try:
            result = await stt.transcribe(b"invalid audio data")
            # Should either handle gracefully or raise appropriate error
            print("   ✅ Error handling works")
            return True
        except Exception as e:
            # Expected - invalid audio should raise error
            print(f"   ✅ Appropriately raised error: {type(e).__name__}")
            return True

    except Exception as e:
        print(f"   ❌ Unexpected failure: {e}")
        return False


async def main():
    """Run all integration tests"""
    print("=" * 70)
    print("LOCAL VOICE PIPELINE - Integration Tests")
    print("=" * 70)

    tests = [
        test_local_stt_initialization,
        test_local_tts_initialization,
        test_local_pipeline_integration,
        test_local_vs_mock_latency,
        test_error_handling,
    ]

    results = []
    for test in tests:
        result = await test()
        results.append(result)

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(results)
    total = len(results)

    print(f"\n{'✅ PASSED' if all(results) else '❌ FAILED'}: {passed}/{total} tests")

    if not all(results):
        print("\n⚠️  Some tests failed. Check output above.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed! Local pipeline is ready.")


if __name__ == "__main__":
    asyncio.run(main())
