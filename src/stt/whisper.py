"""
Whisper API implementation for STT
Uses OpenAI's Whisper API for speech-to-text

Production-grade implementation with:
- Automatic audio normalization
- Retry logic with exponential backoff
- Rate limiting
- Comprehensive error handling
- Edge case validation
"""

import asyncio
import aiohttp
import logging
from typing import Optional
from ..audio.types import AudioData, AudioFormat
from ..audio.normalize import normalize_for_whisper, detect_silence
from ..audio.exceptions import (
    WhisperAPIError,
    WhisperRateLimitError,
    WhisperAuthenticationError,
    WhisperTimeoutError,
    AudioTooShortError,
    AudioTooLongError
)
from ..core.events import EventObserver, EventType
from ..core.retry import RetryConfig, retry_async, RateLimiter

logger = logging.getLogger(__name__)


class WhisperSTT:
    """
    OpenAI Whisper API implementation

    Pricing: $0.006 per minute of audio
    Quality: Industry-leading accuracy
    Latency: ~500-1000ms typical

    Features:
    - Automatic audio normalization to 16kHz mono WAV
    - Retry with exponential backoff on failures
    - Rate limiting (50 req/min default for OpenAI)
    - Timeout handling (30s default)
    - Silence detection
    - Comprehensive error handling
    """

    API_URL = "https://api.openai.com/v1/audio/transcriptions"
    DEFAULT_TIMEOUT_SECONDS = 30.0
    DEFAULT_RATE_LIMIT = 50.0 / 60.0  # 50 requests per minute

    def __init__(
        self,
        api_key: str,
        auto_normalize: bool = True,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_per_second: Optional[float] = None
    ):
        """
        Initialize Whisper STT

        Args:
            api_key: OpenAI API key
            auto_normalize: Automatically normalize audio to 16kHz mono WAV (default True)
            timeout_seconds: Request timeout (default 30s)
            retry_config: Retry configuration (default: 3 attempts with exponential backoff)
            rate_limit_per_second: Rate limit (default: 50 req/min)
        """
        self.api_key = api_key
        self.auto_normalize = auto_normalize
        self.timeout_seconds = timeout_seconds
        self.retry_config = retry_config or RetryConfig(max_attempts=3)
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter(
            tokens_per_second=rate_limit_per_second or self.DEFAULT_RATE_LIMIT
        )

        # Metrics tracking
        self.total_requests = 0
        self.failed_requests = 0
        self.total_latency_ms = 0.0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def transcribe(
        self,
        audio: AudioData,
        observer: Optional[EventObserver] = None,
        detect_silence_threshold: Optional[float] = 0.01
    ) -> str:
        """
        Transcribe audio using Whisper API

        Production-grade implementation with:
        - Automatic normalization to 16kHz mono WAV
        - Silence detection
        - Retry logic on failures
        - Rate limiting
        - Comprehensive error handling

        Args:
            audio: Audio data (any format, will be normalized)
            observer: Optional event observer
            detect_silence_threshold: RMS threshold for silence detection
                                     (None to disable, default 0.01)

        Returns:
            Transcribed text

        Raises:
            WhisperAPIError: If API request fails after retries
            WhisperAuthenticationError: If API key is invalid
            WhisperRateLimitError: If rate limit exceeded
            WhisperTimeoutError: If request times out
            AudioTooShortError: If audio is too short
            AudioTooLongError: If audio exceeds size limit
        """
        self.total_requests += 1
        start_time = asyncio.get_event_loop().time()

        try:
            # Silence detection
            if detect_silence_threshold is not None and detect_silence(audio, detect_silence_threshold):
                logger.warning("Audio appears to be silent, transcription may fail")
                if observer:
                    observer.emit(
                        EventType.STT_START,
                        {"warning": "silent_audio_detected"}
                    )

            # Normalize audio if enabled
            processed_audio = audio
            if self.auto_normalize:
                logger.debug("Normalizing audio for Whisper API")
                processed_audio = normalize_for_whisper(audio)

            # Emit start event
            if observer:
                observer.emit(
                    EventType.STT_START,
                    {
                        "audio_duration_ms": processed_audio.duration_ms,
                        "audio_size_kb": processed_audio.size_kb,
                        "format": processed_audio.format.value,
                        "normalized": self.auto_normalize
                    }
                )

            # Apply rate limiting
            await self._rate_limiter.acquire()

            # Make API call with retry logic
            transcribed_text = await retry_async(
                self._transcribe_api_call,
                processed_audio,
                config=self.retry_config,
                retryable_exceptions=(
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    WhisperRateLimitError
                ),
                on_retry=lambda e, attempt: logger.warning(
                    f"Whisper API retry {attempt}/{self.retry_config.max_attempts}: {e}"
                )
            )

            # Calculate total latency
            end_time = asyncio.get_event_loop().time()
            latency_ms = (end_time - start_time) * 1000
            self.total_latency_ms += latency_ms

            # Emit complete event
            if observer:
                observer.emit(
                    EventType.STT_COMPLETE,
                    {
                        "text": transcribed_text,
                        "latency_ms": latency_ms,
                        "text_length": len(transcribed_text)
                    }
                )

            logger.info(f"Transcription successful ({latency_ms:.0f}ms): {transcribed_text[:50]}...")
            return transcribed_text

        except (AudioTooShortError, AudioTooLongError) as e:
            # Don't retry on validation errors
            self.failed_requests += 1
            if observer:
                observer.emit(
                    EventType.STT_ERROR,
                    {"error": str(e), "error_type": type(e).__name__}
                )
            logger.error(f"Audio validation failed: {e}")
            raise

        except Exception as e:
            self.failed_requests += 1
            if observer:
                observer.emit(
                    EventType.STT_ERROR,
                    {"error": str(e), "error_type": type(e).__name__}
                )
            logger.error(f"Transcription failed: {e}")
            raise

    async def _transcribe_api_call(self, audio: AudioData) -> str:
        """
        Make single API call to Whisper (without retry logic)

        Args:
            audio: Normalized audio data

        Returns:
            Transcribed text

        Raises:
            WhisperAPIError: On API errors
            WhisperAuthenticationError: On auth errors
            WhisperRateLimitError: On rate limit
            WhisperTimeoutError: On timeout
        """
        try:
            # Prepare form data
            form_data = aiohttp.FormData()
            form_data.add_field(
                'file',
                audio.data,
                filename=f'audio.{audio.format.value}',
                content_type=self._get_content_type(audio.format)
            )
            form_data.add_field('model', 'whisper-1')

            # Make API request with timeout
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

            async with session.post(
                self.API_URL,
                headers={'Authorization': f'Bearer {self.api_key}'},
                data=form_data,
                timeout=timeout
            ) as response:
                # Handle specific error codes
                if response.status == 401:
                    raise WhisperAuthenticationError()
                elif response.status == 429:
                    # Extract retry-after header if available
                    retry_after = response.headers.get('Retry-After')
                    retry_seconds = float(retry_after) if retry_after else None
                    raise WhisperRateLimitError(retry_seconds)
                elif response.status >= 400:
                    error_text = await response.text()
                    raise WhisperAPIError(
                        f"API error {response.status}: {error_text}",
                        status_code=response.status
                    )

                result = await response.json()

            return result.get('text', '').strip()

        except asyncio.TimeoutError as e:
            raise WhisperTimeoutError(
                f"Request timed out after {self.timeout_seconds}s"
            ) from e
        except (WhisperAPIError, WhisperAuthenticationError, WhisperRateLimitError, WhisperTimeoutError):
            # Re-raise our custom exceptions
            raise
        except aiohttp.ClientError as e:
            raise WhisperAPIError(f"HTTP client error: {e}") from e

    def get_metrics(self) -> dict:
        """
        Get performance metrics

        Returns:
            Dict with total_requests, failed_requests, avg_latency_ms, success_rate
        """
        success_rate = 1.0 - (self.failed_requests / self.total_requests) if self.total_requests > 0 else 0.0
        avg_latency = self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0

        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency
        }

    def _get_content_type(self, format: AudioFormat) -> str:
        """Get MIME content type for audio format"""
        content_types = {
            AudioFormat.WAV: 'audio/wav',
            AudioFormat.MP3: 'audio/mpeg',
            AudioFormat.FLAC: 'audio/flac',
        }
        return content_types.get(format, 'application/octet-stream')

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
