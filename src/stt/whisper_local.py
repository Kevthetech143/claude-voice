"""
Local Whisper STT using faster-whisper
Zero API cost, fully offline, privacy-preserving, 4x faster than openai-whisper
"""

import asyncio
import tempfile
import os
import logging
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel

from ..audio.types import AudioData, AudioFormat
from ..audio.normalize import normalize_for_whisper
from ..audio.exceptions import STTError, AudioFormatError
from ..core.events import EventObserver, EventType

logger = logging.getLogger(__name__)


class WhisperEngine:
    """
    Whisper engine using faster-whisper library

    faster-whisper is 4x faster than openai-whisper and uses less memory.
    Uses CTranslate2 for optimized inference.
    """

    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",  # int8, float16, float32
        auto_normalize: bool = True,
        language: str = "en"
    ):
        """
        Initialize faster-whisper STT

        Args:
            model_name: Model size (tiny, base, small, medium, large-v2)
            device: Device to run on (cpu or cuda)
            compute_type: Quantization type (int8 for CPU, float16 for GPU)
            auto_normalize: Auto-normalize audio to 16kHz mono WAV
            language: Language code (default: en)
        """
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.auto_normalize = auto_normalize
        self.language = language

        # Load model (downloaded to ~/.cache/huggingface/hub/ on first use)
        logger.info(f"Loading faster-whisper {model_name} model...")
        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type
        )
        logger.info(f"faster-whisper {model_name} model loaded")

        # Metrics
        self.total_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0.0

    async def transcribe(
        self,
        audio: AudioData,
        observer: Optional[EventObserver] = None
    ) -> str:
        """
        Transcribe audio using faster-whisper

        Args:
            audio: Audio data (any format, will be normalized)
            observer: Optional event observer

        Returns:
            Transcribed text

        Raises:
            STTError: If transcription fails
        """
        self.total_requests += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Normalize audio if enabled
            processed_audio = audio
            if self.auto_normalize:
                logger.debug("Normalizing audio for Whisper")
                processed_audio = normalize_for_whisper(audio)

            # Emit start event
            if observer:
                observer.emit(
                    EventType.STT_START,
                    {
                        "audio_duration_ms": processed_audio.duration_ms,
                        "audio_size_kb": processed_audio.size_kb,
                        "format": processed_audio.format.value,
                        "model": self.model_name,
                        "local": True,
                        "engine": "faster-whisper"
                    }
                )

            # Write audio to temporary file
            with tempfile.NamedTemporaryFile(
                suffix='.wav',
                delete=False
            ) as tmp_file:
                tmp_path = tmp_file.name
                tmp_file.write(processed_audio.data)

            try:
                # Run transcription in thread pool (faster-whisper is blocking)
                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(
                    None,
                    self._transcribe_sync,
                    tmp_path
                )

                # Calculate latency
                end_time = asyncio.get_event_loop().time()
                latency_ms = (end_time - start_time) * 1000
                self.total_latency_ms += latency_ms

                # Emit complete event
                if observer:
                    observer.emit(
                        EventType.STT_COMPLETE,
                        {
                            "text": text,
                            "latency_ms": latency_ms,
                            "text_length": len(text),
                            "local": True,
                            "engine": "faster-whisper"
                        }
                    )

                logger.info(f"Transcription successful ({latency_ms:.0f}ms): {text[:50]}...")
                return text

            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            self.failed_requests += 1
            if observer:
                observer.emit(
                    EventType.STT_ERROR,
                    {"error": str(e), "error_type": type(e).__name__, "local": True}
                )
            logger.error(f"Transcription failed: {e}")
            raise STTError(f"faster-whisper transcription failed: {e}") from e

    def _transcribe_sync(self, audio_path: str) -> str:
        """
        Synchronous transcription (runs in thread pool)

        Args:
            audio_path: Path to WAV audio file

        Returns:
            Transcribed text string
        """
        # Transcribe with faster-whisper
        segments, info = self.model.transcribe(
            audio_path,
            language=self.language,
            beam_size=5,
            vad_filter=False  # VAD disabled (onnxruntime incompatible with macOS 13.2)
        )

        # Combine all segments into single text
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text)

        text = " ".join(text_parts).strip()
        return text

    def get_metrics(self) -> dict:
        """Get performance metrics"""
        success_rate = 1.0 - (self.failed_requests / self.total_requests) if self.total_requests > 0 else 0.0
        avg_latency = self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0

        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "model": self.model_name,
            "local": True,
            "engine": "faster-whisper"
        }


class LocalWhisperSTT:
    """
    Factory wrapper for LocalWhisperSTT matching ProviderFactory interface
    """

    def __init__(self, model_name: str = "small", use_gpu: bool = False, observer=None):
        """
        Initialize Local Whisper STT with faster-whisper

        Args:
            model_name: Model size (tiny, base, small, medium, large-v2)
            use_gpu: Use GPU acceleration (requires CUDA)
            observer: Event observer for monitoring
        """
        device = "cuda" if use_gpu else "cpu"
        compute_type = "float16" if use_gpu else "int8"  # int8 for CPU efficiency

        # Create underlying engine
        self._engine = WhisperEngine(
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            auto_normalize=True,
            language="en"
        )

        self.observer = observer
        self.model_name = model_name

    async def transcribe(self, audio: AudioData, observer=None) -> str:
        """Transcribe audio to text"""
        obs = observer or self.observer
        return await self._engine.transcribe(audio, obs)

    def get_metrics(self) -> dict:
        """Get performance metrics from engine"""
        return self._engine.get_metrics()
