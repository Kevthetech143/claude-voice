"""
Unit tests for provider configuration and factory
"""

import pytest
from src.core.providers import ProviderConfig, ProviderFactory, ProviderType


def test_provider_config_local_only():
    """Test local-only configuration"""
    config = ProviderConfig.local_only()

    assert config.stt_provider == ProviderType.WHISPER_LOCAL
    assert config.tts_provider == ProviderType.PIPER_LOCAL
    assert config.whisper_model == "small"
    assert config.enable_fallback is False


def test_provider_config_fast():
    """Test fast configuration"""
    config = ProviderConfig.fast()

    assert config.stt_provider == ProviderType.WHISPER_LOCAL
    assert config.tts_provider == ProviderType.MACOS_SAY
    assert config.whisper_model == "tiny"
    assert config.low_latency_mode is True


def test_provider_config_balanced():
    """Test balanced configuration"""
    config = ProviderConfig.balanced()

    assert config.stt_provider == ProviderType.WHISPER_LOCAL
    assert config.tts_provider == ProviderType.PIPER_LOCAL
    assert config.enable_fallback is True


def test_provider_config_high_quality():
    """Test high quality configuration"""
    config = ProviderConfig.high_quality()

    assert config.whisper_model == "medium"
    assert config.enable_fallback is True


def test_provider_factory_creates_mock_stt():
    """Test factory creates mock STT provider"""
    config = ProviderConfig(
        stt_provider=ProviderType.MOCK_STT,
        tts_provider=ProviderType.MOCK_TTS
    )

    stt = ProviderFactory.create_stt_provider(config)
    assert stt is not None
    assert hasattr(stt, 'transcribe')


def test_provider_factory_creates_mock_tts():
    """Test factory creates mock TTS provider"""
    config = ProviderConfig(
        stt_provider=ProviderType.MOCK_STT,
        tts_provider=ProviderType.MOCK_TTS
    )

    tts = ProviderFactory.create_tts_provider(config)
    assert tts is not None
    assert hasattr(tts, 'speak')


def test_provider_factory_requires_api_keys():
    """Test factory validates API keys"""
    config = ProviderConfig(
        stt_provider=ProviderType.WHISPER_API,
        whisper_api_key=None
    )

    with pytest.raises(ValueError, match="OPENAI_API_KEY required"):
        ProviderFactory.create_stt_provider(config)

    config = ProviderConfig(
        tts_provider=ProviderType.ELEVENLABS_API,
        elevenlabs_api_key=None
    )

    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY required"):
        ProviderFactory.create_tts_provider(config)


def test_provider_factory_invalid_provider():
    """Test factory rejects invalid providers"""
    config = ProviderConfig()
    config.stt_provider = "invalid_provider"

    with pytest.raises(ValueError, match="Unknown STT provider"):
        ProviderFactory.create_stt_provider(config)
