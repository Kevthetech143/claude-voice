#!/usr/bin/env python3
"""
Quick demo - runs 3 test queries to show it working
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src" / "llm"))
from claude_code_session import ClaudeCodeSession


async def quick_demo():
    """Run a few test queries"""

    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Quick Demo")
    print("=" * 70)

    # Create session
    session = ClaudeCodeSession(
        system_message="You are Claude, a helpful voice assistant. Be very concise.",
        timeout_seconds=60,
    )

    print(f"\n✅ Session: {session.session_id[:8]}...\n")

    # Test queries
    queries = [
        "What's your name?",
        "What MCP tools can you access?",
        "Remember: my favorite color is purple",
        "What's my favorite color?",
    ]

    for query in queries:
        print(f"👤 You: {query}")
        print("🤖 Claude: ", end="", flush=True)

        try:
            async for chunk in session.query_stream(query):
                print(chunk, end="", flush=True)
            print()

            metrics = session.get_metrics()
            print(f"💰 Turn {metrics['turn_count']} | Cost: ${metrics['total_cost_usd']:.4f}")
            print()

        except Exception as e:
            print(f"\n❌ Error: {e}\n")

    # Summary
    metrics = session.get_metrics()
    print("=" * 70)
    print(f"✅ Demo complete!")
    print(f"📊 {metrics['turn_count']} turns | ${metrics['total_cost_usd']:.4f} total")
    print("=" * 70)

    print("\n💡 For interactive mode, run:")
    print("   python3 test_interactive.py")
    print()


if __name__ == "__main__":
    asyncio.run(quick_demo())
