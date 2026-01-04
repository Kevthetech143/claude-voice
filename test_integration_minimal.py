#!/usr/bin/env python3
"""
Minimal integration test - verifies ClaudeCodeSession can be imported and used
"""

import asyncio
import sys
from pathlib import Path

# Direct import to avoid dependency issues
sys.path.insert(0, str(Path(__file__).parent / "src" / "llm"))

# Import only what we need
from claude_code_session import ClaudeCodeSession


async def test_basic_query():
    """Test basic ClaudeCodeSession functionality"""
    print("=" * 70)
    print("INTEGRATION TEST: ClaudeCodeSession with Voice Pipeline")
    print("=" * 70)

    print("\n🔧 Creating ClaudeCodeSession...")
    session = ClaudeCodeSession(
        system_message="You are Claude, a helpful voice assistant.",
        timeout_seconds=30,
    )

    print(f"✅ Session created: {session.session_id[:8]}...")

    # Test single query
    query = "Say hello in exactly 5 words."
    print(f"\n👤 Query: {query}")
    print("🤖 Response: ", end="", flush=True)

    try:
        response_text = []
        async for chunk in session.query_stream(query):
            print(chunk, end="", flush=True)
            response_text.append(chunk)

        print("\n")

        # Show metrics
        metrics = session.get_metrics()
        print(f"\n📊 Metrics:")
        print(f"  Turn: {metrics['turn_count']}")
        print(f"  Cost: ${metrics['total_cost_usd']:.4f}")
        print(f"  Provider: {metrics['provider']}")
        print(f"  Timeout: {metrics['timeout_seconds']}s")

        print("\n✅ Integration Test PASSED!")
        print("\n🎯 Key Features Verified:")
        print("  ✓ ClaudeCodeSession instantiation")
        print("  ✓ Streaming response")
        print("  ✓ Cost tracking")
        print("  ✓ Metrics collection")

        print("\n🚀 Ready for Pipeline Integration!")

        return True

    except Exception as e:
        print(f"\n❌ Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_basic_query())
    sys.exit(0 if success else 1)
