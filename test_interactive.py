#!/usr/bin/env python3
"""
Interactive Claude Code CLI Test
Type queries and get voice responses
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src" / "llm"))
from claude_code_session import ClaudeCodeSession


async def interactive_session():
    """Interactive conversation with Claude Code CLI"""

    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Interactive Test")
    print("=" * 70)

    print("\n🎯 Features:")
    print("  ✓ Uses your Claude Code subscription")
    print("  ✓ Full MCP tools access")
    print("  ✓ Session persistence (remembers conversation)")
    print("  ✓ Cost tracking")

    print("\n💡 Type 'quit' or 'exit' to stop")
    print("=" * 70)

    # Create session
    session = ClaudeCodeSession(
        system_message="You are Claude, a helpful voice assistant. Be concise and friendly.",
        timeout_seconds=60,
    )

    print(f"\n✅ Session started: {session.session_id[:8]}...\n")

    while True:
        # Get user input
        try:
            user_input = input("👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("\n👋 Goodbye!")
            break

        # Get Claude's response
        print("🤖 Claude: ", end="", flush=True)

        try:
            async for chunk in session.query_stream(user_input):
                print(chunk, end="", flush=True)
            print()  # New line after response

            # Show metrics
            metrics = session.get_metrics()
            print(f"💰 Turn {metrics['turn_count']} | Cost: ${metrics['total_cost_usd']:.4f}")
            print()

        except asyncio.TimeoutError:
            print("\n⏱️  Timeout - query took too long")
            print()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print()

    # Final summary
    metrics = session.get_metrics()
    print("\n" + "=" * 70)
    print("📊 Session Summary")
    print("=" * 70)
    print(f"  Total turns: {metrics['turn_count']}")
    print(f"  Total cost: ${metrics['total_cost_usd']:.4f}")
    print(f"  Session ID: {metrics['session_id'][:16]}...")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(interactive_session())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
