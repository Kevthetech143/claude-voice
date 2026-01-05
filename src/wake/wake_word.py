"""
Wake word detection using openWakeWord
Enables hands-free voice activation via "hey jarvis" (similar to "claude")
"""

import asyncio
import numpy as np
import logging
from typing import Optional, Callable
from openwakeword.model import Model
from openwakeword.vad import VAD

logger = logging.getLogger(__name__)


class WakeWordDetector:
    """
    Detects wake word in continuous audio stream
    Uses openWakeWord for efficient on-device detection

    The "hey_jarvis" model is used as it sounds similar to "claude"
    and provides good detection accuracy without requiring custom training.
    """

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.75,  # Balanced threshold (0.75) - provides 870% margin above max silence score (0.08)
        sample_rate: int = 16000,
        chunk_duration_ms: int = 80  # 80ms = 1280 samples (openWakeWord requirement)
    ):
        """
        Initialize wake word detector

        Args:
            model_name: Wake word model to use (default: "hey_jarvis")
            threshold: Detection confidence threshold 0.0-1.0 (default: 0.5)
            sample_rate: Audio sample rate in Hz (default: 16000)
            chunk_duration_ms: Audio chunk size in milliseconds (default: 100)
        """
        self.model_name = model_name
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)

        # Load wake word model
        logger.info(f"Loading wake word model: {model_name}")
        self.model = Model(wakeword_models=[model_name])
        logger.info(f"Wake word model loaded: {model_name}")

        # Load VAD (Voice Activity Detection)
        # VAD filters out non-speech audio (music, TV, typing, background noise)
        # This prevents false triggers from non-speech sounds
        self.vad = VAD()
        logger.info("VAD (Voice Activity Detection) enabled")

        # Metrics
        self.total_detections = 0
        self.false_positives = 0

    async def listen_for_wake_word(
        self,
        callback: Callable,
        observer=None
    ):
        """
        Continuously listen for wake word and trigger callback when detected

        Args:
            callback: Async function to call when wake word is detected
            observer: Optional event observer for monitoring

        This runs in an infinite loop, processing audio chunks and detecting
        the wake word. When detected, it calls the callback function.
        """
        import pyaudio

        logger.info(f"Starting wake word detection (model: {self.model_name}, threshold: {self.threshold})")

        p = pyaudio.PyAudio()

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            logger.info("Audio stream opened for wake word detection")

            while True:
                try:
                    # Read audio chunk (non-blocking with exception handling)
                    chunk = stream.read(self.chunk_size, exception_on_overflow=False)

                    # Convert bytes to numpy array (int16)
                    audio_data = np.frombuffer(chunk, dtype=np.int16)

                    # VAD (Voice Activity Detection) - filter non-speech audio
                    # This prevents false triggers from music, TV, typing, background noise
                    # Uses frame_size=640 (40ms) for clean division
                    # chunk_size=1280 divides evenly: 1280 ÷ 640 = 2 chunks
                    vad_result = self.vad.predict(audio_data, frame_size=640)
                    speech_prob = float(np.mean(vad_result)) if isinstance(vad_result, np.ndarray) else float(vad_result)

                    # Only run wake word detection if speech detected
                    if speech_prob < 0.5:
                        # Not speech - skip wake word detection
                        logger.debug(f"VAD: speech_prob={speech_prob:.4f} (skipping - not speech)")
                        await asyncio.sleep(0.01)
                        continue

                    # Speech detected - run wake word detection
                    prediction = self.model.predict(audio_data)
                    score = prediction.get(self.model_name, 0.0)

                    # Debug logging - shows VAD + wake word scores
                    print(f"[WAKE_DEBUG] vad={speech_prob:.4f} score={score:.4f} threshold={self.threshold:.2f} triggered={score > self.threshold}")
                    logger.debug(f"vad={speech_prob:.4f} score={score:.4f} threshold={self.threshold:.2f} triggered={score > self.threshold}")

                    # Check if wake word detected
                    if score > self.threshold:
                        self.total_detections += 1

                        logger.info(f"Wake word detected! (score: {score:.3f}, threshold: {self.threshold})")

                        # Note: wake_word_detected event not in EventType enum yet
                        # Future: Add WAKE_WORD_DETECTED to events.py EventType enum

                        # Call callback function (async)
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()

                        # CRITICAL: Reset model internal state after detection
                        # Without this, the model stays "activated" and outputs high scores
                        # even during silence, causing spurts of false positives
                        self.model.reset()
                        self.vad.reset_states()
                        logger.debug("Model and VAD states reset after detection")

                        # Cooldown period after detection (1.0s prevents double-trigger while feeling responsive)
                        await asyncio.sleep(1.0)

                    # Small delay to prevent tight loop
                    await asyncio.sleep(0.01)

                except Exception as e:
                    logger.error(f"Error in wake word detection loop: {e}")
                    # Continue listening even if there's an error
                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Fatal error in wake word detector: {e}")
            raise

        finally:
            # Cleanup
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
            p.terminate()
            logger.info("Wake word detection stopped")

    def get_metrics(self) -> dict:
        """
        Get wake word detection metrics

        Returns:
            Dict with detection statistics
        """
        return {
            "model": self.model_name,
            "threshold": self.threshold,
            "total_detections": self.total_detections,
            "false_positives": self.false_positives,
            "sample_rate": self.sample_rate,
            "chunk_duration_ms": self.chunk_duration_ms
        }
