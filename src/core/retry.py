"""
Retry logic with exponential backoff
Production-grade error handling for API calls
"""

import asyncio
import logging
from typing import TypeVar, Callable, Optional, Type
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay_ms: float = 100.0,
        max_delay_ms: float = 10000.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration

        Args:
            max_attempts: Maximum number of attempts (default 3)
            initial_delay_ms: Initial delay in milliseconds (default 100ms)
            max_delay_ms: Maximum delay cap (default 10s)
            exponential_base: Base for exponential backoff (default 2.0)
            jitter: Add random jitter to prevent thundering herd (default True)
        """
        self.max_attempts = max_attempts
        self.initial_delay_ms = initial_delay_ms
        self.max_delay_ms = max_delay_ms
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay_ms(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in milliseconds
        """
        # Exponential backoff
        delay = self.initial_delay_ms * (self.exponential_base ** attempt)

        # Cap at max delay
        delay = min(delay, self.max_delay_ms)

        # Add jitter (±25%)
        if self.jitter:
            import random
            jitter_factor = 1.0 + (random.random() - 0.5) * 0.5
            delay *= jitter_factor

        return delay


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    **kwargs
) -> T:
    """
    Retry an async function with exponential backoff

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration (default: 3 attempts)
        retryable_exceptions: Exceptions that trigger retry
        on_retry: Callback called on each retry (exception, attempt_number)
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries exhausted
    """
    if config is None:
        config = RetryConfig()

    last_exception: Optional[Exception] = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)

        except retryable_exceptions as e:
            last_exception = e

            # If last attempt, raise
            if attempt == config.max_attempts - 1:
                logger.error(
                    f"All {config.max_attempts} retry attempts exhausted for {func.__name__}"
                )
                raise

            # Calculate delay
            delay_ms = config.get_delay_ms(attempt)

            # Log retry
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                f"Retrying in {delay_ms:.0f}ms..."
            )

            # Call retry callback
            if on_retry:
                on_retry(e, attempt + 1)

            # Wait before retry
            await asyncio.sleep(delay_ms / 1000.0)

    # Should never reach here, but for type safety
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error: no exception raised")


def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for automatic retry on async functions

    Example:
        @with_retry(config=RetryConfig(max_attempts=5),
                    retryable_exceptions=(aiohttp.ClientError,))
        async def call_api():
            ...

    Args:
        config: Retry configuration
        retryable_exceptions: Exceptions that trigger retry

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func,
                *args,
                config=config,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )
        return wrapper
    return decorator


class RateLimiter:
    """
    Token bucket rate limiter

    Prevents exceeding API rate limits
    """

    def __init__(
        self,
        tokens_per_second: float,
        bucket_size: Optional[int] = None
    ):
        """
        Initialize rate limiter

        Args:
            tokens_per_second: Rate limit (e.g., 50 for 50 requests/second)
            bucket_size: Bucket size (default: tokens_per_second)
        """
        self.tokens_per_second = tokens_per_second
        self.bucket_size = bucket_size or int(tokens_per_second)
        self.tokens = float(self.bucket_size)
        self.last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens (wait if necessary)

        Args:
            tokens: Number of tokens to acquire (default 1)
        """
        async with self._lock:
            while True:
                now = asyncio.get_event_loop().time()
                elapsed = now - self.last_update

                # Refill tokens
                self.tokens = min(
                    self.bucket_size,
                    self.tokens + elapsed * self.tokens_per_second
                )
                self.last_update = now

                # Check if we have enough tokens
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Wait for tokens to refill
                wait_time = (tokens - self.tokens) / self.tokens_per_second
                await asyncio.sleep(wait_time)
