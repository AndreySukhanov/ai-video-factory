"""
Retry utilities with exponential backoff for video generation.
"""
import asyncio
import functools
import random
import time
from typing import Callable, Optional, Tuple, Type, Union
from dataclasses import dataclass


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd

    # Error classification
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        TimeoutError,
        ConnectionError,
        OSError,
    )
    # Strings in error messages that indicate retryable errors
    retryable_error_messages: Tuple[str, ...] = (
        "timeout",
        "timed out",
        "connection",
        "rate limit",
        "too many requests",
        "service unavailable",
        "internal server error",
        "502",
        "503",
        "504",
    )
    # Strings that indicate non-retryable errors (fail fast)
    # Note: "moderation" removed — handled by PromptSoftener at generation level
    non_retryable_messages: Tuple[str, ...] = (
        "invalid",
        "not found",
        "unauthorized",
        "forbidden",
        "bad request",
    )


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay with exponential backoff and optional jitter."""
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add ±25% jitter
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)

    return max(0.1, delay)  # Minimum 100ms delay


def is_retryable_error(error: Exception, config: RetryConfig) -> bool:
    """Determine if an error is retryable."""
    # Check exception type
    if isinstance(error, config.retryable_exceptions):
        return True

    error_str = str(error).lower()

    # Check for non-retryable messages first (fail fast)
    for msg in config.non_retryable_messages:
        if msg in error_str:
            return False

    # Check for retryable messages
    for msg in config.retryable_error_messages:
        if msg in error_str:
            return True

    # Default: retry on unknown errors (safer for API calls)
    return True


def retry_sync(
    func: Optional[Callable] = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator for synchronous functions with retry logic.

    Usage:
        @retry_sync(max_attempts=3, base_delay=1.0)
        def my_function():
            ...

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        on_retry: Optional callback called on each retry (attempt, error, delay)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(config.max_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Check if we should retry
                    if attempt + 1 >= config.max_attempts:
                        print(f"[RETRY] {fn.__name__}: All {config.max_attempts} attempts failed")
                        raise

                    if not is_retryable_error(e, config):
                        print(f"[RETRY] {fn.__name__}: Non-retryable error: {e}")
                        raise

                    # Calculate delay
                    delay = calculate_delay(attempt, config)

                    print(f"[RETRY] {fn.__name__}: Attempt {attempt + 1}/{config.max_attempts} failed: {e}")
                    print(f"[RETRY] {fn.__name__}: Retrying in {delay:.1f}s...")

                    if on_retry:
                        on_retry(attempt + 1, e, delay)

                    time.sleep(delay)

            # Should not reach here, but just in case
            raise last_error

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


async def retry_async(
    func: Optional[Callable] = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator for async functions with retry logic.

    Usage:
        @retry_async(max_attempts=3, base_delay=1.0)
        async def my_function():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(config.max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if attempt + 1 >= config.max_attempts:
                        print(f"[RETRY] {fn.__name__}: All {config.max_attempts} attempts failed")
                        raise

                    if not is_retryable_error(e, config):
                        print(f"[RETRY] {fn.__name__}: Non-retryable error: {e}")
                        raise

                    delay = calculate_delay(attempt, config)

                    print(f"[RETRY] {fn.__name__}: Attempt {attempt + 1}/{config.max_attempts} failed: {e}")
                    print(f"[RETRY] {fn.__name__}: Retrying in {delay:.1f}s...")

                    if on_retry:
                        on_retry(attempt + 1, e, delay)

                    await asyncio.sleep(delay)

            raise last_error

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable:
    """
    Standalone retry wrapper for calling any function with retry.

    Usage:
        result = with_retry(max_attempts=3)(lambda: some_api_call())

    Or with progress callback:
        def on_retry(attempt, error, delay):
            send_progress(f"Retry {attempt}: {error}")

        result = with_retry(max_attempts=3, on_retry=on_retry)(api_call)
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    def execute(fn: Callable, *args, **kwargs):
        last_error = None

        for attempt in range(config.max_attempts):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt + 1 >= config.max_attempts:
                    raise

                if not is_retryable_error(e, config):
                    raise

                delay = calculate_delay(attempt, config)

                print(f"[RETRY] Attempt {attempt + 1}/{config.max_attempts} failed: {e}")
                print(f"[RETRY] Retrying in {delay:.1f}s...")

                if on_retry:
                    on_retry(attempt + 1, e, delay)

                time.sleep(delay)

        raise last_error

    return execute
