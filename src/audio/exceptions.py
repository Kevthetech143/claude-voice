"""
Audio pipeline exceptions
Specific exceptions for production-grade error handling
"""
from typing import Optional


class AudioPipelineError(Exception):
    """Base exception for all audio pipeline errors"""
    pass


class AudioCaptureError(AudioPipelineError):
    """Error during audio capture"""
    pass


class MicrophonePermissionDeniedError(AudioCaptureError):
    """Microphone access permission denied by OS"""
    pass


class MicrophoneNotFoundError(AudioCaptureError):
    """No microphone device found"""
    pass


class AudioFormatError(AudioPipelineError):
    """Invalid audio format or corrupted audio data"""
    pass


class AudioTooShortError(AudioFormatError):
    """Audio duration too short for processing"""
    def __init__(self, duration_ms: float, minimum_ms: float):
        self.duration_ms = duration_ms
        self.minimum_ms = minimum_ms
        super().__init__(
            f"Audio too short: {duration_ms}ms (minimum: {minimum_ms}ms)"
        )


class AudioTooLongError(AudioFormatError):
    """Audio duration too long for processing"""
    def __init__(self, size_mb: float, maximum_mb: float):
        self.size_mb = size_mb
        self.maximum_mb = maximum_mb
        super().__init__(
            f"Audio too large: {size_mb:.1f}MB (maximum: {maximum_mb}MB)"
        )


class AudioNormalizationError(AudioPipelineError):
    """Error during audio normalization (resampling, conversion)"""
    pass


class STTError(AudioPipelineError):
    """Base exception for STT errors"""
    pass


class WhisperAPIError(STTError):
    """Error calling Whisper API"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class WhisperRateLimitError(WhisperAPIError):
    """Whisper API rate limit exceeded"""
    def __init__(self, retry_after_seconds: Optional[float] = None):
        self.retry_after_seconds = retry_after_seconds
        message = "Whisper API rate limit exceeded"
        if retry_after_seconds:
            message += f" (retry after {retry_after_seconds}s)"
        super().__init__(message, status_code=429)


class WhisperAuthenticationError(WhisperAPIError):
    """Invalid Whisper API key"""
    def __init__(self):
        super().__init__("Invalid OpenAI API key", status_code=401)


class WhisperTimeoutError(STTError):
    """Whisper API request timeout"""
    pass


class TTSError(AudioPipelineError):
    """Base exception for TTS errors"""
    pass


class TTSGenerationError(TTSError):
    """Error generating speech from text"""
    pass


class MacOSSayNotAvailableError(TTSError):
    """macOS say command not available (non-macOS system)"""
    pass


class ElevenLabsAPIError(TTSError):
    """Error calling ElevenLabs API"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)


class ElevenLabsRateLimitError(ElevenLabsAPIError):
    """ElevenLabs API rate limit exceeded"""
    def __init__(self, retry_after_seconds: Optional[float] = None):
        self.retry_after_seconds = retry_after_seconds
        message = "ElevenLabs API rate limit exceeded"
        if retry_after_seconds:
            message += f" (retry after {retry_after_seconds}s)"
        super().__init__(message, status_code=429)


from typing import Optional
