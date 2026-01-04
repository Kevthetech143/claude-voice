"""
Unit tests for model download and caching
"""

import pytest
from pathlib import Path
from src.core.models import ModelManager, ModelInfo


@pytest.fixture
def temp_cache(tmp_path):
    """Create temporary cache directory"""
    return tmp_path / "test_cache"


def test_model_manager_initialization(temp_cache):
    """Test ModelManager creates cache directories"""
    manager = ModelManager(cache_dir=temp_cache)

    assert manager.cache_dir == temp_cache
    assert manager.whisper_dir.exists()
    assert manager.piper_dir.exists()


def test_model_manager_default_cache():
    """Test ModelManager uses default cache location"""
    manager = ModelManager()

    expected_cache = Path.home() / ".cache" / "claude-voice"
    assert manager.cache_dir == expected_cache


def test_whisper_models_defined():
    """Test Whisper models are properly defined"""
    models = ModelManager.WHISPER_MODELS

    assert "tiny" in models
    assert "base" in models
    assert "small" in models
    assert "medium" in models

    # Check model info structure
    for name, info in models.items():
        assert isinstance(info, ModelInfo)
        assert info.name.startswith("ggml-")
        assert info.name.endswith(".bin")
        assert info.url.startswith("https://")
        assert info.size_mb > 0


def test_piper_voices_defined():
    """Test Piper voices are properly defined"""
    voices = ModelManager.PIPER_VOICES

    assert "en_US-lessac-medium" in voices
    assert "en_US-amy-medium" in voices

    # Check voice info structure
    for name, info in voices.items():
        assert isinstance(info, ModelInfo)
        assert info.url.startswith("https://")
        assert info.size_mb > 0


def test_get_whisper_model_path_invalid(temp_cache):
    """Test error on invalid Whisper model"""
    manager = ModelManager(cache_dir=temp_cache)

    with pytest.raises(ValueError, match="Unknown Whisper model"):
        manager.get_whisper_model_path("invalid_model")


def test_get_piper_voice_path_invalid(temp_cache):
    """Test error on invalid Piper voice"""
    manager = ModelManager(cache_dir=temp_cache)

    with pytest.raises(ValueError, match="Unknown Piper voice"):
        manager.get_piper_voice_path("invalid_voice")


def test_list_cached_models_empty(temp_cache):
    """Test listing cached models when none exist"""
    manager = ModelManager(cache_dir=temp_cache)
    cached = manager.list_cached_models()

    assert cached['whisper'] == []
    assert cached['piper'] == []


def test_list_cached_models_with_whisper(temp_cache):
    """Test listing cached Whisper models"""
    manager = ModelManager(cache_dir=temp_cache)

    # Create fake cached model
    whisper_path = manager.whisper_dir / "ggml-tiny.bin"
    whisper_path.touch()

    cached = manager.list_cached_models()

    assert "tiny" in cached['whisper']
    assert cached['piper'] == []


def test_list_cached_models_with_piper(temp_cache):
    """Test listing cached Piper models"""
    manager = ModelManager(cache_dir=temp_cache)

    # Create fake cached voice
    voice_dir = manager.piper_dir / "en_US-lessac-medium"
    voice_dir.mkdir(parents=True)

    cached = manager.list_cached_models()

    assert cached['whisper'] == []
    assert "en_US-lessac-medium" in cached['piper']


def test_get_cache_size_mb_empty(temp_cache):
    """Test cache size calculation when empty"""
    manager = ModelManager(cache_dir=temp_cache)
    size = manager.get_cache_size_mb()

    assert size == 0.0


def test_get_cache_size_mb_with_files(temp_cache):
    """Test cache size calculation with files"""
    manager = ModelManager(cache_dir=temp_cache)

    # Create test file
    test_file = manager.whisper_dir / "test.bin"
    test_file.write_bytes(b"x" * 1024 * 1024)  # 1MB

    size = manager.get_cache_size_mb()

    assert size >= 1.0
    assert size < 1.1  # Should be close to 1MB


def test_clear_cache(temp_cache):
    """Test cache clearing"""
    manager = ModelManager(cache_dir=temp_cache)

    # Create test files
    (manager.whisper_dir / "test.bin").write_bytes(b"test")
    (manager.piper_dir / "test.onnx").write_bytes(b"test")

    # Clear cache
    manager.clear_cache()

    # Verify directories exist but are empty
    assert manager.whisper_dir.exists()
    assert manager.piper_dir.exists()
    assert len(list(manager.whisper_dir.iterdir())) == 0
    assert len(list(manager.piper_dir.iterdir())) == 0
