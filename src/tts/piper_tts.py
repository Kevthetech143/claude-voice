"""
Piper TTS implementation with Jarvis voice
Uses jgkawell/jarvis model from HuggingFace for Paul Bettany's Jarvis voice
"""

import asyncio
import wave
import tempfile
import os
from typing import Optional
from pathlib import Path
from piper import PiperVoice
from huggingface_hub import hf_hub_download
from ..audio.types import AudioData, AudioFormat
from ..core.events import EventObserver, EventType


class PiperTTS:
    """
    Piper TTS implementation with Jarvis voice from Iron Man

    Uses pre-trained jgkawell/jarvis model for British accent voice
    similar to Paul Bettany's portrayal in Marvel movies.

    Advantages:
    - Authentic Jarvis-like voice
    - Fast (1-2 seconds per sentence on CPU)
    - No GPU required
    - Completely local/offline
    - No API costs

    Disadvantages:
    - Slightly slower than macOS say (~1 second added latency)
    - Requires model download (~14MB one-time)
    """

    def __init__(self, model_quality: str = "medium"):
        """
        Initialize Piper TTS with Jarvis voice

        Args:
            model_quality: Quality level - "low", "medium", or "high"
                          Medium is recommended (good quality, fast)
        """
        self.model_quality = model_quality
        self._voice = None
        self._model_path = None
        self._config_path = None

    def _load_model(self):
        """Lazy load the Piper voice model"""
        if self._voice is not None:
            return

        # Download model files if not already cached
        repo_id = "jgkawell/jarvis"
        model_file = f"en/en_GB/jarvis/{self.model_quality}/jarvis-{self.model_quality}.onnx"
        config_file = f"en/en_GB/jarvis/{self.model_quality}/jarvis-{self.model_quality}.onnx.json"

        self._model_path = hf_hub_download(repo_id=repo_id, filename=model_file)
        self._config_path = hf_hub_download(repo_id=repo_id, filename=config_file)

        # Load voice
        self._voice = PiperVoice.load(self._model_path, config_path=self._config_path)

    async def speak(
        self,
        text: str,
        observer: Optional[EventObserver] = None
    ) -> None:
        """
        Convert text to speech and play it using Piper + Jarvis voice

        Args:
            text: Text to speak
            observer: Optional event observer

        Raises:
            RuntimeError: If TTS generation fails
        """
        # Emit start event
        if observer:
            observer.emit(
                EventType.TTS_START,
                {
                    "text": text,
                    "text_length": len(text),
                    "voice": "jarvis",
                    "quality": self.model_quality
                }
            )

        start_time = asyncio.get_event_loop().time()

        try:
            # Load model if needed (lazy loading)
            self._load_model()

            # Generate speech in a thread pool (Piper is CPU-bound)
            # synthesize() returns a generator of AudioChunk objects
            loop = asyncio.get_event_loop()
            audio_chunks = await loop.run_in_executor(
                None,
                lambda: list(self._voice.synthesize(text))
            )

            # Concatenate all audio chunks (extract bytes from AudioChunk objects)
            all_audio = b''.join(chunk.audio_int16_bytes for chunk in audio_chunks)

            # Save to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_path = tmp_file.name

                # Write WAV data
                with wave.open(tmp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(22050)  # Piper default sample rate
                    wav_file.writeframes(all_audio)

            # Play audio using macOS afplay
            process = await asyncio.create_subprocess_exec(
                'afplay',
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise RuntimeError(f"afplay failed: {error_msg}")

            # Calculate latency
            end_time = asyncio.get_event_loop().time()
            latency_ms = (end_time - start_time) * 1000

            # Estimate duration (16-bit audio at 22050 Hz)
            duration_ms = (len(all_audio) / 2) / 22.050

            # Emit complete event
            if observer:
                observer.emit(
                    EventType.TTS_COMPLETE,
                    {
                        "latency_ms": latency_ms,
                        "estimated_duration_ms": duration_ms
                    }
                )

        except Exception as e:
            # Emit error event
            if observer:
                observer.emit(
                    EventType.TTS_ERROR,
                    {"error": str(e), "error_type": type(e).__name__}
                )
            raise

    @staticmethod
    def get_available_qualities() -> list[str]:
        """
        Get available quality levels for Jarvis voice

        Returns:
            List of quality options: ["low", "medium", "high"]
        """
        return ["low", "medium", "high"]
