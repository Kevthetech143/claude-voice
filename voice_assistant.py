#!/usr/bin/env python3
"""
CLAUDE VOICE ASSISTANT
Real voice assistant using Claude Code CLI

Usage:
  python3 voice_assistant.py        # Text mode (type to chat)
  python3 voice_assistant.py --voice  # Voice mode (requires microphone)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src" / "llm"))
sys.path.insert(0, str(Path(__file__).parent / "src" / "tts"))

from claude_code_session import ClaudeCodeSession
from macos_say import MacOSSayTTS


async def text_mode():
    """Interactive text chat with voice responses"""

    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Text Mode")
    print("=" * 70)

    print("\n🎯 How it works:")
    print("  1. You type your message")
    print("  2. Claude responds (text + voice)")
    print("  3. Using your Claude Code subscription")
    print("  4. Full MCP tools access")

    print("\n💡 Type 'quit' to exit")
    print("=" * 70)

    # Create session
    llm = ClaudeCodeSession(
        system_message="You are Claude, a helpful voice assistant. Be concise and friendly.",
        timeout_seconds=60,
    )

    # Create TTS for voice output
    tts = MacOSSayTTS(voice="Samantha")

    print(f"\n✅ Session ready: {llm.session_id[:8]}...\n")

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

        response_text = []
        try:
            async for chunk in llm.query_stream(user_input):
                print(chunk, end="", flush=True)
                response_text.append(chunk)
            print()

            # Speak the response
            full_response = "".join(response_text)
            if full_response.strip():
                print("🔊 Speaking...", end="", flush=True)
                await tts.speak(full_response)
                print(" done")

            # Show metrics
            metrics = llm.get_metrics()
            print(f"💰 Turn {metrics['turn_count']} | Cost: ${metrics['total_cost_usd']:.4f}")
            print()

        except asyncio.TimeoutError:
            print("\n⏱️  Timeout - query took too long")
            print()
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print()

    # Final summary
    metrics = llm.get_metrics()
    print("\n" + "=" * 70)
    print("📊 Session Summary")
    print("=" * 70)
    print(f"  Total turns: {metrics['turn_count']}")
    print(f"  Total cost: ${metrics['total_cost_usd']:.4f}")
    print("=" * 70)


async def voice_mode():
    """Full voice mode - requires microphone and whisper.cpp"""

    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Voice Mode")
    print("=" * 70)

    print("\n⚠️  Voice mode requires:")
    print("  • whisper.cpp installed")
    print("  • Microphone access")
    print("  • ggml-small.bin model (~465MB)")

    print("\n❌ Voice mode not yet implemented")
    print("   BETA is building LocalWhisperSTT component")

    print("\n💡 For now, use text mode:")
    print("   python3 voice_assistant.py")


async def main():
    """Main entry point"""

    # Check if voice mode requested
    if len(sys.argv) > 1 and sys.argv[1] == "--voice":
        await voice_mode()
    else:
        await text_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
