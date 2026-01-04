"""
Provider selection and configuration
Supports local and API-based STT/TTS providers
"""

from enum import Enum
from dataclasses import dataclass
from typing import Literal


class ProviderType(str, Enum):
    """Provider types for STT, LLM, and TTS"""

    # STT Providers
    WHISPER_API = "whisper_api"  # OpenAI Whisper API (cloud)
    WHISPER_LOCAL = "whisper_local"  # whisper.cpp (local)
    MOCK_STT = "mock_stt"  # Mock for testing

    # LLM Providers
    CLAUDE_CODE_CLI = "claude_code_cli"  # Claude Code CLI (local)
    CLAUDE_API = "claude_api"  # Anthropic API (cloud)
    MOCK_LLM = "mock_llm"  # Mock for testing

    # TTS Providers
    MACOS_SAY = "macos_say"  # macOS built-in (local)
    PIPER_LOCAL = "piper_local"  # Piper TTS (local)
    ELEVENLABS_API = "elevenlabs_api"  # ElevenLabs (cloud)
    MOCK_TTS = "mock_tts"  # Mock for testing


@dataclass
class ProviderConfig:
    """Configuration for voice providers"""

    # STT Configuration
    stt_provider: ProviderType = ProviderType.WHISPER_LOCAL
    whisper_model: Literal["tiny", "base", "small", "medium", "large"] = "small"
    whisper_api_key: str | None = None  # For API mode

    # LLM Configuration
    llm_provider: ProviderType = ProviderType.CLAUDE_CODE_CLI
    llm_system_message: str | None = "You are Claude, a helpful voice assistant."
    llm_timeout_seconds: int = 120
    anthropic_api_key: str | None = None  # For API mode

    # TTS Configuration
    tts_provider: ProviderType = ProviderType.PIPER_LOCAL
    piper_voice: str = "en_US-lessac-medium"  # Natural voice
    macos_voice: str = "Samantha"
    elevenlabs_api_key: str | None = None  # For API mode
    elevenlabs_voice_id: str | None = None

    # Performance
    use_gpu: bool = True  # Use Metal on Mac
    low_latency_mode: bool = False  # Trade quality for speed

    # Fallback
    enable_fallback: bool = True  # Fall back to API if local fails

    @classmethod
    def local_only(cls) -> "ProviderConfig":
        """Configuration for fully local operation (no APIs)

        Uses whisper.cpp for STT, Claude Code CLI for LLM, and macOS say for TTS.
        Note: Piper TTS has dependency issues (onnxruntime) - use MACOS_SAY instead.
        """
        return cls(
            stt_provider=ProviderType.WHISPER_LOCAL,
            llm_provider=ProviderType.CLAUDE_CODE_CLI,
            tts_provider=ProviderType.MACOS_SAY,  # Piper blocked by deps - using say
            whisper_model="small",
            enable_fallback=False,
        )

    @classmethod
    def api_only(cls) -> "ProviderConfig":
        """Configuration for API-based operation"""
        return cls(
            stt_provider=ProviderType.WHISPER_API,
            llm_provider=ProviderType.CLAUDE_API,
            tts_provider=ProviderType.ELEVENLABS_API,
            enable_fallback=False,
        )

    @classmethod
    def balanced(cls) -> "ProviderConfig":
        """Balanced: local with API fallback

        Uses local Whisper + Claude Code CLI + macOS say.
        Advanced users can manually install Piper and use PIPER_LOCAL.
        """
        return cls(
            stt_provider=ProviderType.WHISPER_LOCAL,
            llm_provider=ProviderType.CLAUDE_CODE_CLI,
            tts_provider=ProviderType.MACOS_SAY,  # Piper available if manually installed
            whisper_model="small",
            enable_fallback=True,
        )

    @classmethod
    def fast(cls) -> "ProviderConfig":
        """Optimized for speed"""
        return cls(
            stt_provider=ProviderType.WHISPER_LOCAL,
            llm_provider=ProviderType.CLAUDE_CODE_CLI,
            tts_provider=ProviderType.MACOS_SAY,
            whisper_model="tiny",
            low_latency_mode=True,
            enable_fallback=False,
        )

    @classmethod
    def high_quality(cls) -> "ProviderConfig":
        """Optimized for quality

        Uses Whisper medium (higher quality STT), Claude Code CLI, with API TTS for natural voice.
        Requires ELEVENLABS_API_KEY for TTS.
        """
        return cls(
            stt_provider=ProviderType.WHISPER_LOCAL,
            llm_provider=ProviderType.CLAUDE_CODE_CLI,
            tts_provider=ProviderType.ELEVENLABS_API,  # Natural voice requires API
            whisper_model="medium",
            enable_fallback=True,
        )


class ProviderFactory:
    """Factory for creating STT/TTS providers based on configuration"""

    @staticmethod
    def create_stt_provider(config: ProviderConfig, observer=None):
        """
        Create STT provider based on configuration

        Args:
            config: Provider configuration
            observer: Event observer

        Returns:
            STT provider instance
        """
        if config.stt_provider == ProviderType.WHISPER_LOCAL:
            from ..stt.whisper_local import LocalWhisperSTT
            return LocalWhisperSTT(
                model_name=config.whisper_model,
                use_gpu=config.use_gpu,
                observer=observer,
            )

        elif config.stt_provider == ProviderType.WHISPER_API:
            from ..stt.whisper import WhisperSTT
            if not config.whisper_api_key:
                raise ValueError("OPENAI_API_KEY required for Whisper API")
            return WhisperSTT(
                api_key=config.whisper_api_key,
                observer=observer,
            )

        elif config.stt_provider == ProviderType.MOCK_STT:
            from ..stt.mock import MockSTT
            return MockSTT()

        else:
            raise ValueError(f"Unknown STT provider: {config.stt_provider}")

    @staticmethod
    def create_tts_provider(config: ProviderConfig, observer=None):
        """
        Create TTS provider based on configuration

        Args:
            config: Provider configuration
            observer: Event observer

        Returns:
            TTS provider instance
        """
        if config.tts_provider == ProviderType.PIPER_LOCAL:
            from ..tts.piper_local import LocalPiperTTS
            return LocalPiperTTS(
                voice_name=config.piper_voice,
                use_gpu=config.use_gpu,
                observer=observer,
            )

        elif config.tts_provider == ProviderType.MACOS_SAY:
            from ..tts.macos_say import MacOSSayTTS
            return MacOSSayTTS(
                voice=config.macos_voice,
                observer=observer,
            )

        elif config.tts_provider == ProviderType.ELEVENLABS_API:
            from ..tts.elevenlabs import ElevenLabsTTS
            if not config.elevenlabs_api_key:
                raise ValueError("ELEVENLABS_API_KEY required for ElevenLabs")
            return ElevenLabsTTS(
                api_key=config.elevenlabs_api_key,
                voice_id=config.elevenlabs_voice_id,
                observer=observer,
            )

        elif config.tts_provider == ProviderType.MOCK_TTS:
            from ..tts.mock import MockTTS
            return MockTTS()

        else:
            raise ValueError(f"Unknown TTS provider: {config.tts_provider}")

    @staticmethod
    def create_llm_provider(config: ProviderConfig, observer=None):
        """
        Create LLM provider based on configuration

        Args:
            config: Provider configuration
            observer: Event observer

        Returns:
            LLM provider instance
        """
        if config.llm_provider == ProviderType.CLAUDE_CODE_CLI:
            from ..llm.claude_code_session import ClaudeCodeSession
            return ClaudeCodeSession(
                system_message=config.llm_system_message,
                observer=observer,
                timeout_seconds=config.llm_timeout_seconds,
            )

        elif config.llm_provider == ProviderType.CLAUDE_API:
            from ..llm.claude_api import ClaudeAPI
            if not config.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY required for Claude API")
            return ClaudeAPI(
                api_key=config.anthropic_api_key,
                observer=observer,
            )

        elif config.llm_provider == ProviderType.MOCK_LLM:
            from ..llm.mock import MockLLM
            return MockLLM(
                response="Mock response for testing",
                observer=observer,
            )

        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")
