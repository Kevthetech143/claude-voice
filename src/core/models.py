"""
Model download and caching system for local models
Handles Whisper and Piper model management
"""

import os
import hashlib
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Literal


@dataclass
class ModelInfo:
    """Information about a downloadable model"""

    name: str
    url: str
    size_mb: int
    sha256: str | None = None
    description: str = ""


class ModelManager:
    """Manages downloading and caching of ML models"""

    # Whisper.cpp models
    WHISPER_MODELS = {
        "tiny": ModelInfo(
            name="ggml-tiny.bin",
            url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
            size_mb=75,
            description="Fastest, lowest quality (75MB)",
        ),
        "base": ModelInfo(
            name="ggml-base.bin",
            url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
            size_mb=142,
            description="Fast, good quality (142MB)",
        ),
        "small": ModelInfo(
            name="ggml-small.bin",
            url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
            size_mb=466,
            description="Balanced quality/speed (466MB)",
        ),
        "medium": ModelInfo(
            name="ggml-medium.bin",
            url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
            size_mb=1500,
            description="High quality, slower (1.5GB)",
        ),
    }

    # Piper TTS voices
    PIPER_VOICES = {
        "en_US-lessac-medium": ModelInfo(
            name="en_US-lessac-medium",
            url="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/",
            size_mb=63,
            description="Natural US English voice",
        ),
        "en_US-amy-medium": ModelInfo(
            name="en_US-amy-medium",
            url="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/",
            size_mb=63,
            description="Clear US English female voice",
        ),
    }

    def __init__(self, cache_dir: Path | str | None = None):
        """
        Initialize model manager

        Args:
            cache_dir: Directory to cache models (default: ~/.cache/claude-voice)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "claude-voice"

        self.cache_dir = Path(cache_dir)
        self.whisper_dir = self.cache_dir / "whisper"
        self.piper_dir = self.cache_dir / "piper"

        # Create directories
        self.whisper_dir.mkdir(parents=True, exist_ok=True)
        self.piper_dir.mkdir(parents=True, exist_ok=True)

    def get_whisper_model_path(
        self, model_name: Literal["tiny", "base", "small", "medium"]
    ) -> Path:
        """
        Get path to Whisper model, downloading if needed

        Args:
            model_name: Model size

        Returns:
            Path to model file

        Raises:
            ValueError: If model name is invalid
        """
        if model_name not in self.WHISPER_MODELS:
            raise ValueError(f"Unknown Whisper model: {model_name}")

        model_info = self.WHISPER_MODELS[model_name]
        model_path = self.whisper_dir / model_info.name

        if not model_path.exists():
            print(f"\n📥 Downloading Whisper {model_name} model ({model_info.size_mb}MB)...")
            print(f"   This is a one-time download. Model will be cached at:")
            print(f"   {model_path}")
            self._download_file(model_info.url, model_path)
            print(f"   ✅ Download complete!")

        return model_path

    def get_piper_voice_path(self, voice_name: str) -> Path:
        """
        Get path to Piper voice model, downloading if needed

        Args:
            voice_name: Voice identifier

        Returns:
            Path to voice directory

        Raises:
            ValueError: If voice name is invalid
        """
        if voice_name not in self.PIPER_VOICES:
            raise ValueError(f"Unknown Piper voice: {voice_name}")

        voice_info = self.PIPER_VOICES[voice_name]
        voice_dir = self.piper_dir / voice_name

        # Check if model files exist
        onnx_path = voice_dir / f"{voice_name}.onnx"
        json_path = voice_dir / f"{voice_name}.onnx.json"

        if not (onnx_path.exists() and json_path.exists()):
            print(f"\n📥 Downloading Piper voice '{voice_name}' ({voice_info.size_mb}MB)...")
            print(f"   This is a one-time download. Voice will be cached at:")
            print(f"   {voice_dir}")
            voice_dir.mkdir(parents=True, exist_ok=True)

            # Download .onnx file
            onnx_url = voice_info.url + f"{voice_name}.onnx"
            self._download_file(onnx_url, onnx_path)

            # Download .onnx.json file
            json_url = voice_info.url + f"{voice_name}.onnx.json"
            self._download_file(json_url, json_path)

            print(f"   ✅ Download complete!")

        return voice_dir

    def _download_file(self, url: str, dest: Path, chunk_size: int = 8192) -> None:
        """
        Download file with progress indication

        Args:
            url: URL to download from
            dest: Destination path
            chunk_size: Download chunk size
        """
        try:
            # Download with progress
            with urllib.request.urlopen(url) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(dest, 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # Progress indicator
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r   Progress: {percent:.1f}%", end='', flush=True)

                print()  # New line after progress

        except Exception as e:
            # Clean up partial download
            if dest.exists():
                dest.unlink()
            raise RuntimeError(f"Failed to download {url}: {e}")

    def list_cached_models(self) -> dict[str, list[str]]:
        """
        List all cached models

        Returns:
            Dict with 'whisper' and 'piper' keys listing cached models
        """
        whisper_cached = []
        for model_name, model_info in self.WHISPER_MODELS.items():
            model_path = self.whisper_dir / model_info.name
            if model_path.exists():
                whisper_cached.append(model_name)

        piper_cached = []
        for voice_name in self.PIPER_VOICES.keys():
            voice_dir = self.piper_dir / voice_name
            if voice_dir.exists():
                piper_cached.append(voice_name)

        return {
            "whisper": whisper_cached,
            "piper": piper_cached,
        }

    def clear_cache(self) -> None:
        """Clear all cached models"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.whisper_dir.mkdir(parents=True, exist_ok=True)
            self.piper_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_size_mb(self) -> float:
        """Get total size of cached models in MB"""
        total_bytes = 0

        for path in self.cache_dir.rglob('*'):
            if path.is_file():
                total_bytes += path.stat().st_size

        return total_bytes / (1024 * 1024)
