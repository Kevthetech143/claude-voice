"""
Tests proving retry logic and rate limiting work correctly
Response to ALPHA's challenge: Show me the tests that prove it works
"""

import pytest
import asyncio
import time
from src.core.retry import RetryConfig, retry_async, RateLimiter


class TestRetryLogic:
    """Prove exponential backoff with jitter works"""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_third_attempt(self):
        """Test that retry eventually succeeds"""
        attempt_count = 0

        async def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError(f"Attempt {attempt_count} failed")
            return "success"

        config = RetryConfig(max_attempts=5, initial_delay_ms=10)
        result = await retry_async(
            flaky_function,
            config=config,
            retryable_exceptions=(ValueError,)
        )

        assert result == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausts_max_attempts(self):
        """Test that retry gives up after max attempts"""
        attempt_count = 0

        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError(f"Attempt {attempt_count} failed")

        config = RetryConfig(max_attempts=3, initial_delay_ms=10)

        with pytest.raises(ValueError) as exc_info:
            await retry_async(
                always_fails,
                config=config,
                retryable_exceptions=(ValueError,)
            )

        assert "Attempt 3 failed" in str(exc_info.value)
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Prove exponential backoff increases delay"""
        attempt_count = 0
        delays = []
        start_time = None

        async def track_delays():
            nonlocal attempt_count, start_time
            if start_time is not None:
                # Calculate time since last attempt
                elapsed = time.time() - start_time
                delays.append(elapsed)

            start_time = time.time()
            attempt_count += 1

            if attempt_count < 4:
                raise ValueError("Not yet")
            return "success"

        config = RetryConfig(
            max_attempts=4,
            initial_delay_ms=100,
            exponential_base=2.0,
            jitter=False  # Disable jitter for predictable timing
        )

        await retry_async(
            track_delays,
            config=config,
            retryable_exceptions=(ValueError,)
        )

        # Verify exponential growth
        # Delays should be approximately: 100ms, 200ms, 400ms
        assert len(delays) == 3

        # Allow 20% tolerance for timing variance
        assert 0.08 < delays[0] < 0.12  # ~100ms
        assert 0.16 < delays[1] < 0.24  # ~200ms
        assert 0.32 < delays[2] < 0.48  # ~400ms

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Prove jitter prevents thundering herd"""
        delays_run1 = []
        delays_run2 = []

        async def failing_func():
            raise ValueError("Always fails")

        config = RetryConfig(
            max_attempts=3,
            initial_delay_ms=100,
            jitter=True
        )

        # Run twice and collect delays
        for delay_list in [delays_run1, delays_run2]:
            start_times = []

            async def track_timing():
                start_times.append(asyncio.get_event_loop().time())
                raise ValueError("Fail")

            try:
                await retry_async(
                    track_timing,
                    config=config,
                    retryable_exceptions=(ValueError,)
                )
            except ValueError:
                pass

            # Calculate delays between attempts
            for i in range(1, len(start_times)):
                delay_list.append(start_times[i] - start_times[i-1])

        # With jitter, delays should be different
        # (very unlikely to be exactly the same)
        assert delays_run1 != delays_run2

    @pytest.mark.asyncio
    async def test_retry_callback_is_called(self):
        """Test that on_retry callback is invoked"""
        retry_attempts = []

        async def flaky():
            if len(retry_attempts) < 2:
                raise ValueError("Fail")
            return "success"

        def on_retry(exception, attempt):
            retry_attempts.append((str(exception), attempt))

        config = RetryConfig(max_attempts=5, initial_delay_ms=10)
        await retry_async(
            flaky,
            config=config,
            retryable_exceptions=(ValueError,),
            on_retry=on_retry
        )

        # Callback should be called twice (attempts 1 and 2)
        assert len(retry_attempts) == 2
        assert retry_attempts[0][1] == 1
        assert retry_attempts[1][1] == 2

    @pytest.mark.asyncio
    async def test_non_retryable_exception_fails_immediately(self):
        """Test that non-retryable exceptions don't retry"""
        attempt_count = 0

        async def raises_type_error():
            nonlocal attempt_count
            attempt_count += 1
            raise TypeError("Not retryable")

        config = RetryConfig(max_attempts=5, initial_delay_ms=10)

        with pytest.raises(TypeError):
            await retry_async(
                raises_type_error,
                config=config,
                retryable_exceptions=(ValueError,)  # Only retry ValueError
            )

        # Should fail immediately, no retries
        assert attempt_count == 1


class TestRateLimiter:
    """Prove rate limiter prevents request overload"""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_within_limit(self):
        """Test that requests within limit are allowed immediately"""
        # 10 requests per second
        limiter = RateLimiter(tokens_per_second=10.0)

        start = asyncio.get_event_loop().time()

        # Acquire 5 tokens (within limit)
        for _ in range(5):
            await limiter.acquire()

        elapsed = asyncio.get_event_loop().time() - start

        # Should complete almost immediately
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_throttles_over_limit(self):
        """Test that requests over limit are throttled"""
        # 2 requests per second (slow rate for testing)
        limiter = RateLimiter(tokens_per_second=2.0, bucket_size=2)

        start = asyncio.get_event_loop().time()

        # Acquire 4 tokens (over limit)
        for _ in range(4):
            await limiter.acquire()

        elapsed = asyncio.get_event_loop().time() - start

        # Should take ~1 second to refill tokens
        # 2 initial tokens used immediately
        # Need to wait for 2 more tokens at 2/sec = 1 second
        assert 0.9 < elapsed < 1.2

    @pytest.mark.asyncio
    async def test_rate_limiter_with_whisper_rate(self):
        """Test rate limiter with realistic Whisper API rate (50/min)"""
        # 50 requests per minute = 0.833 requests per second
        limiter = RateLimiter(tokens_per_second=50.0/60.0, bucket_size=5)

        start = asyncio.get_event_loop().time()

        # Make 10 requests
        for _ in range(10):
            await limiter.acquire()

        elapsed = asyncio.get_event_loop().time() - start

        # First 5 immediate (bucket), next 5 throttled
        # At 0.833 req/sec, 5 more requests take ~6 seconds
        # Allow some tolerance
        assert 4.5 < elapsed < 7.0

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_requests(self):
        """Test rate limiter with concurrent requests"""
        limiter = RateLimiter(tokens_per_second=5.0, bucket_size=2)

        async def make_request(request_id):
            await limiter.acquire()
            return request_id

        start = asyncio.get_event_loop().time()

        # Launch 5 concurrent requests
        results = await asyncio.gather(*[
            make_request(i) for i in range(5)
        ])

        elapsed = asyncio.get_event_loop().time() - start

        # All 5 should complete
        assert len(results) == 5

        # Should be throttled (not all immediate)
        assert elapsed > 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
