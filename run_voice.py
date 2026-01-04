#!/usr/bin/env python3
"""
VOICE ASSISTANT - Speak and get voice responses
Requires: whisper.cpp, microphone access
"""

import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Check dependencies first
try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False

from src.llm.claude_code_session import ClaudeCodeSession
from src.stt.whisper_local import LocalWhisperSTT
from src.tts.piper_tts import PiperTTS
from src.audio.types import AudioData, AudioFormat
from src.core.events import InMemoryEventObserver
from src.wake.wake_word import WakeWordDetector


class MicrophoneCapture:
    """Simple microphone capture using PyAudio"""

    def __init__(self, duration_seconds: int = 5):
        """
        Args:
            duration_seconds: How long to record (default: 5s)
        """
        self.duration = duration_seconds
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1024

    async def capture(self) -> AudioData:
        """Record audio from microphone"""
        print(f"🎤 Recording for {self.duration} seconds... SPEAK NOW!")

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        audio_bytes, num_frames = await loop.run_in_executor(None, self._record)

        print("✅ Recording complete")

        # Calculate actual duration from recorded frames (BETA fix)
        actual_duration_ms = (num_frames / self.sample_rate) * 1000

        return AudioData(
            data=audio_bytes,
            sample_rate=self.sample_rate,
            format=AudioFormat.WAV,
            channels=self.channels,
            duration_ms=actual_duration_ms
        )

    def _record(self) -> tuple[bytes, int]:
        """Synchronous recording (runs in thread pool)

        Returns:
            Tuple of (WAV audio bytes, total frame count)
        """
        import pyaudio
        import wave
        import io

        try:
            p = pyaudio.PyAudio()

            # Check if microphone is available
            if p.get_default_input_device_info() is None:
                raise RuntimeError("No microphone found")

            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
        except OSError as e:
            raise RuntimeError(
                f"Microphone access failed: {e}\n"
                "Check permissions in System Preferences > Security & Privacy > Microphone"
            )

        try:
            frames = []
            num_chunks = int(self.sample_rate / self.chunk_size * self.duration)

            for _ in range(num_chunks):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)

        finally:
            # Always cleanup, even on error
            stream.stop_stream()
            stream.close()
            p.terminate()

        # Calculate total frames recorded
        total_frames = len(frames) * self.chunk_size

        # Convert to WAV format
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.setcomptype('NONE', 'not compressed')  # BETA fix: explicit compression
            wf.writeframes(b''.join(frames))

        return wav_buffer.getvalue(), total_frames


async def voice_assistant():
    """Full voice assistant loop"""

    print("=" * 70)
    print("CLAUDE VOICE ASSISTANT - Full Voice Mode with Wake Word")
    print("=" * 70)

    print("\n🎯 How it works:")
    print("  1. Say 'hey jarvis' to activate")
    print("  2. Speak your question (8 seconds)")
    print("  3. Claude transcribes + responds (text + voice)")
    print("  4. Returns to listening mode")
    print("  5. Press Ctrl+C to exit")

    print("\n💡 Using:")
    print("  • openWakeWord (wake word detection)")
    print("  • Your microphone (PyAudio)")
    print("  • faster-whisper (local STT)")
    print("  • Claude Code CLI (your subscription)")
    print("  • macOS say (voice output)")

    print("=" * 70)

    # Create components
    observer = InMemoryEventObserver()

    mic = MicrophoneCapture(duration_seconds=8)
    stt = LocalWhisperSTT(model_name="small", observer=observer)
    llm = ClaudeCodeSession(
        system_message="You are Claude, a helpful voice assistant. Be concise and friendly.",
        observer=observer,
        timeout_seconds=180  # 3 minutes for Chrome automation tasks (navigation, page loads, form filling)
    )
    tts = PiperTTS(model_quality="high")  # Jarvis voice from Iron Man (highest quality)

    print(f"\n✅ Session: {llm.session_id[:8]}...\n")

    # Create wake word detector - threshold 0.75 provides 870% margin above max silence score (0.08)
    wake_word = WakeWordDetector(model_name="hey_jarvis", threshold=0.75)

    # Define the callback for when wake word is detected
    async def on_wake_word_detected():
        """Called when wake word is detected"""
        print("🎯 Wake word detected!")

        try:
            # Audio acknowledgment - Jarvis says "Yes sir"
            print("🔊 Jarvis: Yes sir")
            await tts.speak("Yes sir", observer=observer)

            # 1. Capture audio
            audio = await mic.capture()

            # 2. Transcribe
            print("🎧 Transcribing...")
            transcript = await stt.transcribe(audio)

            if not transcript or transcript.strip() == "":
                print("❌ No speech detected. Try speaking louder.")
                print("👂 Listening for wake word...\n")
                return

            print(f"📝 You said: {transcript}")

            # 3. Get Claude's response
            print("🤖 Claude: ", end="", flush=True)

            response_text = []
            async for chunk in llm.query_stream(transcript):
                print(chunk, end="", flush=True)
                response_text.append(chunk)
            print()

            # 4. Speak response
            full_response = "".join(response_text)
            if full_response.strip():
                print("🔊 Speaking...")
                await tts.speak(full_response, observer=observer)

            # Show metrics
            metrics = llm.get_metrics()
            print(f"💰 Turn {metrics['turn_count']} | Cost: ${metrics['total_cost_usd']:.4f}")
            print("👂 Listening for wake word...\n")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            print("👂 Listening for wake word...\n")

    # Start listening for wake word (runs until Ctrl+C)
    print("👂 Listening for wake word 'hey jarvis'...")
    print("💡 Say 'hey jarvis' to activate\n")

    try:
        await wake_word.listen_for_wake_word(on_wake_word_detected, observer=observer)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()

    # Final summary
    metrics = llm.get_metrics()
    print("\n" + "=" * 70)
    print("📊 Session Summary")
    print("=" * 70)
    print(f"  Total turns: {metrics['turn_count']}")
    print(f"  Total cost: ${metrics['total_cost_usd']:.4f}")
    print("=" * 70)


async def main():
    """Main entry point with dependency checks"""

    # Check PyAudio
    if not HAS_PYAUDIO:
        print("=" * 70)
        print("❌ PyAudio not installed")
        print("=" * 70)
        print("\nVoice mode requires PyAudio for microphone access.")
        print("\n💡 Install with:")
        print("   brew install portaudio")
        print("   pip3 install pyaudio")
        print("\nOr use text mode:")
        print("   python3 voice_assistant.py")
        return

    # Check faster-whisper
    try:
        import faster_whisper
    except ImportError:
        print("=" * 70)
        print("❌ faster-whisper not installed")
        print("=" * 70)
        print("\nVoice mode requires faster-whisper for local STT.")
        print("\n💡 Install with:")
        print("   source venv_py312/bin/activate")
        print("   pip install faster-whisper pyaudio openwakeword")
        return

    # Check openwakeword
    try:
        import openwakeword
    except ImportError:
        print("=" * 70)
        print("❌ openwakeword not installed")
        print("=" * 70)
        print("\nWake word detection requires openwakeword.")
        print("\n💡 Install with:")
        print("   source venv_py312/bin/activate")
        print("   pip install openwakeword")
        return

    # All good - run voice assistant
    await voice_assistant()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
