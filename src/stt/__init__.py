"""
Speech-to-Text (STT) module
Converts audio to text using Whisper API, local Whisper, or mock implementations
"""

from .protocol import STTProvider
from .whisper import WhisperSTT
from .whisper_local import LocalWhisperSTT
from .mock import MockSTT

__all__ = ["STTProvider", "WhisperSTT", "LocalWhisperSTT", "MockSTT"]
