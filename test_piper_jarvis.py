"""
Test script for Piper TTS with Jarvis voice
"""

import asyncio
import sys
sys.path.insert(0, '~/claude-voice')

from src.tts.piper_tts import PiperTTS


async def test_jarvis():
    """Test Jarvis voice"""
    print("🎙️ Initializing Jarvis voice...")
    tts = PiperTTS(model_quality="medium")

    test_phrases = [
        "Good morning, sir. All systems are online.",
        "I have completed the requested analysis.",
        "Shall I render using current specifications, or iterate?"
    ]

    for phrase in test_phrases:
        print(f"\n📢 Speaking: '{phrase}'")
        try:
            await tts.speak(phrase)
            print("✅ Success!")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    print("\n🎉 All tests passed! Jarvis voice is working!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_jarvis())
    sys.exit(0 if success else 1)
