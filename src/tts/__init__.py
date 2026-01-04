"""
Text-to-Speech (TTS) module
Converts text to audio using macOS say, ElevenLabs, or mock implementations
"""

from .protocol import TTSProvider
from .macos_say import MacOSSayTTS
from .mock import MockTTS

__all__ = ["TTSProvider", "MacOSSayTTS", "MockTTS"]
