"""Configuration management"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


@dataclass
class Config:
    """Application configuration"""

    # API Keys (from environment)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    elevenlabs_api_key: str | None = None

    # STT Configuration
    stt_provider: Literal["whisper", "mock"] = "whisper"

    # TTS Configuration
    tts_provider: Literal["macos_say", "elevenlabs", "mock"] = "macos_say"
    tts_voice: str = "Daniel"  # For macOS say
    elevenlabs_model: str = "eleven_turbo_v2_5"  # For ElevenLabs
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice

    # Claude Configuration
    claude_model: str = "claude-sonnet-4-5-20250929"
    claude_max_tokens: int = 1024
    claude_system_prompt: str = (
        "You are Claude, a helpful voice assistant. "
        "Keep responses SHORT and conversational (2-3 sentences max). "
        "Speak naturally like you're having a conversation."
    )

    # Pipeline Configuration
    enable_sentence_chunking: bool = True
    sentence_min_length: int = 10  # Minimum chars before emitting sentence

    # Audio Configuration
    audio_sample_rate: int = 16000  # 16kHz for Whisper
    audio_channels: int = 1  # Mono
    audio_chunk_duration_ms: int = 100  # Buffer size

    # Testing
    test_mode: bool = False  # If True, use mock providers

    # Logging
    log_level: str = "INFO"
    log_file: Path | None = Path("/tmp/claude-voice.log")


def load_config(env_file: Path | str | None = None) -> Config:
    """
    Load configuration from environment variables

    Args:
        env_file: Optional .env file path. If None, searches for .env in current directory.

    Returns:
        Config instance with values from environment
    """
    # Load .env file if it exists
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()  # Searches for .env in current directory

    config = Config()

    # API Keys (required for production)
    config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    config.openai_api_key = os.getenv("OPENAI_API_KEY")
    config.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

    # Provider selection
    config.stt_provider = os.getenv("STT_PROVIDER", "whisper")  # type: ignore
    config.tts_provider = os.getenv("TTS_PROVIDER", "macos_say")  # type: ignore

    # Test mode
    test_mode_env = os.getenv("TEST_MODE", "false").lower()
    config.test_mode = test_mode_env in ("true", "1", "yes")

    if config.test_mode:
        # Override to use mocks
        config.stt_provider = "mock"
        config.tts_provider = "mock"

    return config


def validate_config(config: Config) -> list[str]:
    """
    Validate configuration

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check API keys for non-mock providers
    if config.stt_provider == "whisper" and not config.openai_api_key:
        errors.append("OPENAI_API_KEY required for Whisper STT")

    if config.tts_provider == "elevenlabs" and not config.elevenlabs_api_key:
        errors.append("ELEVENLABS_API_KEY required for ElevenLabs TTS")

    # Note: We use Claude via MCP (existing subscription), not API key
    # MCP handles authentication automatically

    return errors
