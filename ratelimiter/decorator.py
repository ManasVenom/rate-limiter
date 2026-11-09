"""
Decorator utilities for rate limiting functions and API handlers.
"""

from functools import wraps
import inspect
from typing import Any, Callable, Optional, Union

from ratelimiter.base import BaseRateLimiter, RateLimitExceeded, RateLimitResult


def _resolve_key(
    key_extractor: Callable[..., Any],
    target_fn: Callable[..., Any],
    args: tuple,
    kwargs: dict,
) -> str:
    """Resolve key from extractor function matching arguments gracefully."""
    # Attempt 1: Direct pass-through
    try:
        return str(key_extractor(*args, **kwargs))
    except TypeError:
        pass

    # Attempt 2: Match parameters by name from bound function signature
    try:
        sig_target = inspect.signature(target_fn)
        bound = sig_target.bind(*args, **kwargs)
        bound.apply_defaults()
        sig_key = inspect.signature(key_extractor)

        filtered = {
            param: bound.arguments[param]
            for param in sig_key.parameters
            if param in bound.arguments
        }
        if len(filtered) == len(sig_key.parameters):
            return str(key_extractor(**filtered))
    except Exception:
        pass

    # Attempt 3: Single positional argument fallback
    if args:
        try:
            return str(key_extractor(args[0]))
        except Exception:
            pass

    return str(key_extractor(*args))


def rate_limit(
    limiter: BaseRateLimiter,
    key: Union[str, Callable[..., str]],
    tokens: int = 1,
    on_limit_exceeded: Optional[Callable[[RateLimitResult, Any, Any], Any]] = None,
):
    """
    Function decorator to enforce rate limits.
    
    Args:
        limiter: An instance of BaseRateLimiter (e.g. TokenBucketLimiter).
        key: A static string key or a callable extracting a key from args/kwargs.
        tokens: Number of tokens to consume per invocation (default 1).
        on_limit_exceeded: Optional callback invoked when rate limit is exceeded.
                           If None, raises `RateLimitExceeded`.
                           
    Example:
        @rate_limit(limiter, key=lambda user_id: f"user:{user_id}")
        def perform_action(user_id: str, payload: dict):
            ...
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if callable(key):
                resolved_key = _resolve_key(key, fn, args, kwargs)
            else:
                resolved_key = str(key)

            result = limiter.acquire(resolved_key, tokens=tokens)
            if not result.allowed:
                if on_limit_exceeded:
                    return on_limit_exceeded(result, *args, **kwargs)
                raise RateLimitExceeded(resolved_key, result)

            return fn(*args, **kwargs)

        return wrapper

    return decorator
