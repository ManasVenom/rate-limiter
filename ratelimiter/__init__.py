"""
Rate Limiter Project: Extensible, high-concurrency rate limiting in Python.
"""

from ratelimiter.base import BaseRateLimiter, RateLimitExceeded, RateLimitResult
from ratelimiter.decorator import rate_limit
from ratelimiter.token_bucket import TokenBucketLimiter

__all__ = [
    "BaseRateLimiter",
    "RateLimitResult",
    "RateLimitExceeded",
    "TokenBucketLimiter",
    "rate_limit",
]

try:
    from ratelimiter.django_middleware import RateLimitMiddleware
    __all__.append("RateLimitMiddleware")
except ImportError:
    pass
