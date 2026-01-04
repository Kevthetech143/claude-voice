#!/usr/bin/env python3
"""
Benchmark: Local vs API Voice Providers
Measures latency, quality, and cost differences
"""

import sys
import asyncio
import time
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

from src.core.providers import ProviderConfig, ProviderFactory
from src.core.pipeline import VoicePipeline
from src.core.events import InMemoryEventObserver
from src.llm.claude_api import ClaudeAPI
from src.llm.chunker_fixed import SentenceChunker


@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""

    config_name: str
    total_latency_ms: float
    stt_latency_ms: float
    llm_latency_ms: float
    tts_latency_ms: float
    total_events: int
    sentences_spoken: int
    errors: list[str]


async def benchmark_config(config_name: str, config: ProviderConfig, test_text: str) -> BenchmarkResult:
    """
    Benchmark a specific configuration

    Args:
        config_name: Name of configuration
        config: Provider configuration to test
        test_text: Input text to process

    Returns:
        Benchmark results
    """
    print(f"\n{'=' * 70}")
    print(f"Benchmarking: {config_name}")
    print(f"{'=' * 70}")

    observer = InMemoryEventObserver()
    errors = []

    try:
        # Create providers
        stt_provider = ProviderFactory.create_stt_provider(config, observer)
        tts_provider = ProviderFactory.create_tts_provider(config, observer)
        llm_provider = ClaudeAPI(
            api_key=config.whisper_api_key or "demo-key",
            system_message="You are Claude. Keep responses brief."
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

        # Run benchmark
        start_time = time.time()
        await pipeline.process_text(test_text)
        end_time = time.time()

        total_latency_ms = (end_time - start_time) * 1000

        # Analyze events
        events = observer.get_events()

        # Calculate component latencies
        stt_events = [e for e in events if 'stt' in e.event_type.value]
        llm_events = [e for e in events if 'llm' in e.event_type.value]
        tts_events = [e for e in events if 'tts' in e.event_type.value]

        stt_latency_ms = 0.0
        if len(stt_events) >= 2:
            stt_latency_ms = (stt_events[-1].timestamp - stt_events[0].timestamp) * 1000

        llm_latency_ms = 0.0
        if len(llm_events) >= 2:
            llm_latency_ms = (llm_events[-1].timestamp - llm_events[0].timestamp) * 1000

        tts_latency_ms = 0.0
        if len(tts_events) >= 2:
            tts_latency_ms = (tts_events[-1].timestamp - tts_events[0].timestamp) * 1000

        sentences_spoken = sum(1 for e in events if e.event_type.value == 'sentence_ready')

        print(f"✅ Success")
        print(f"   • Total: {total_latency_ms:.0f}ms")
        print(f"   • STT: {stt_latency_ms:.0f}ms")
        print(f"   • LLM: {llm_latency_ms:.0f}ms")
        print(f"   • TTS: {tts_latency_ms:.0f}ms")
        print(f"   • Sentences: {sentences_spoken}")

        return BenchmarkResult(
            config_name=config_name,
            total_latency_ms=total_latency_ms,
            stt_latency_ms=stt_latency_ms,
            llm_latency_ms=llm_latency_ms,
            tts_latency_ms=tts_latency_ms,
            total_events=len(events),
            sentences_spoken=sentences_spoken,
            errors=errors
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        errors.append(str(e))

        return BenchmarkResult(
            config_name=config_name,
            total_latency_ms=0.0,
            stt_latency_ms=0.0,
            llm_latency_ms=0.0,
            tts_latency_ms=0.0,
            total_events=0,
            sentences_spoken=0,
            errors=errors
        )


async def main():
    """Run comprehensive benchmark"""
    print("=" * 70)
    print("VOICE PIPELINE BENCHMARK - Local vs API")
    print("=" * 70)

    test_text = "What are the benefits of local voice processing?"

    # Test configurations
    configs = [
        ("Local Only", ProviderConfig.local_only()),
        ("Fast (Tiny + macOS Say)", ProviderConfig.fast()),
        ("Balanced (Local + API Fallback)", ProviderConfig.balanced()),
        ("High Quality (Medium + Piper)", ProviderConfig.high_quality()),
    ]

    results = []

    for config_name, config in configs:
        try:
            result = await benchmark_config(config_name, config, test_text)
            results.append(result)
        except Exception as e:
            print(f"\n❌ Failed to benchmark {config_name}: {e}")

    # Print comparison table
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)

    if not results:
        print("\n❌ No successful benchmarks")
        return

    print("\n📊 Latency Comparison:")
    print(f"\n{'Configuration':<30} {'Total':<10} {'STT':<10} {'LLM':<10} {'TTS':<10}")
    print("-" * 70)

    for result in results:
        if result.errors:
            status = "ERROR"
        else:
            status = f"{result.total_latency_ms:>6.0f}ms"

        print(
            f"{result.config_name:<30} "
            f"{status:<10} "
            f"{result.stt_latency_ms:>6.0f}ms "
            f"{result.llm_latency_ms:>6.0f}ms "
            f"{result.tts_latency_ms:>6.0f}ms"
        )

    # Find fastest
    successful = [r for r in results if not r.errors]
    if successful:
        fastest = min(successful, key=lambda r: r.total_latency_ms)
        print(f"\n🏆 Fastest: {fastest.config_name} ({fastest.total_latency_ms:.0f}ms)")

    # Cost analysis
    print("\n💰 Cost Analysis:")
    print("   • Local models: $0 per use (one-time download)")
    print("   • API models: $X per minute (ongoing cost)")
    print("   • Break-even: After Y hours of use")

    # Quality notes
    print("\n🎯 Quality Notes:")
    print("   • Local Whisper: Comparable to API (same model)")
    print("   • Piper TTS: Natural but less expressive than ElevenLabs")
    print("   • macOS Say: Fast but robotic")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
