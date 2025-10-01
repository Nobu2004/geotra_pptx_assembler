import time
import functools
from typing import Callable, TypeVar, Optional
from .exceptions import LLMRateLimitError, LLMAPIError, LLMTimeoutError

T = TypeVar('T')


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry decorator with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    # Don't retry on authentication errors
                    if "authentication" in str(e).lower() or "api key" in str(e).lower():
                        raise
                    
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        # Last attempt failed
                        raise LLMAPIError(
                            message=f"Failed after {max_attempts} attempts",
                            error_type="retry_exhausted",
                            original_error=e
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def with_timeout(seconds: float):
    """
    Timeout decorator
    
    Note: This is a simple implementation. For production,
    consider using threading or asyncio for proper timeout handling.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Simple implementation - actual timeout would need threading
            # This is a placeholder for the concept
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_request(func: Callable[..., T]) -> Callable[..., T]:
    """Log API requests for debugging"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        provider = args[0].__class__.__name__ if args else "Unknown"
        print(f"[{provider}] Calling {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            print(f"[{provider}] {func.__name__} succeeded")
            return result
        except Exception as e:
            print(f"[{provider}] {func.__name__} failed: {e}")
            raise
    
    return wrapper