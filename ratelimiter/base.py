"""
Base abstractions and models for rate limiters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Dict, Optional


class RateLimitResult:
    """
    Result of a rate limit check.
    Uses __slots__ for maximum throughput and minimal memory overhead.
    
    Attributes:
        allowed: True if the request is permitted, False if rate limited.
        remaining: The estimated number of tokens/requests remaining in the current window/bucket.
        retry_after: Seconds to wait before a rejected request could potentially succeed (0.0 if allowed).
        reset_after: Seconds until the rate limit quota fully resets/refills to max capacity.
        limit: The maximum limit configured for this bucket/window.
    """
    __slots__ = ("allowed", "remaining", "retry_after", "reset_after", "limit")

    def __init__(
        self,
        allowed: bool,
        remaining: float,
        retry_after: float,
        reset_after: float,
        limit: float,
    ):
        self.allowed = allowed
        self.remaining = remaining
        self.retry_after = retry_after
        self.reset_after = reset_after
        self.limit = limit

    def __repr__(self) -> str:
        return (
            f"RateLimitResult(allowed={self.allowed}, remaining={self.remaining}, "
            f"retry_after={self.retry_after}, reset_after={self.reset_after}, limit={self.limit})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, RateLimitResult):
            return False
        return (
            self.allowed == other.allowed
            and self.remaining == other.remaining
            and self.retry_after == other.retry_after
            and self.reset_after == other.reset_after
            and self.limit == other.limit
        )

    def to_headers(self) -> Dict[str, str]:
        """
        Generate standard HTTP rate limiting headers for API gateways.
        Compatible with RFC 6585 (429 Too Many Requests) and common gateway conventions.
        """
        rem_int = int(self.remaining)
        reset_int = math.ceil(self.reset_after)
        headers = {
            "X-RateLimit-Limit": str(int(self.limit)),
            "X-RateLimit-Remaining": str(rem_int if rem_int > 0 else 0),
            "X-RateLimit-Reset": str(reset_int if reset_int > 0 else 0),
        }
        if not self.allowed:
            retry_int = math.ceil(self.retry_after)
            headers["Retry-After"] = str(retry_int if retry_int > 1 else 1)
        return headers


class RateLimitExceeded(Exception):
    """Exception raised when an operation exceeds its rate limit."""

    def __init__(self, key: str, result: RateLimitResult):
        self.key = key
        self.result = result
        super().__init__(
            f"Rate limit exceeded for key '{key}'. "
            f"Retry after {result.retry_after:.2f} seconds."
        )


class BaseRateLimiter(ABC):
    """
    Abstract base class for all rate limiting algorithms.
    Supports pluggable backends (In-memory, Redis, Memcached, etc.).
    """

    @abstractmethod
    def acquire(self, key: str, tokens: int = 1) -> RateLimitResult:
        """
        Attempt to consume `tokens` for the specified `key`.
        
        Args:
            key: Unique identifier for the subject (e.g., user_id, IP address, API key).
            tokens: Number of tokens/requests to consume (default: 1).
            
        Returns:
            RateLimitResult containing approval status, remaining tokens, and retry timings.
        """
        pass

    def is_allowed(self, key: str, tokens: int = 1) -> bool:
        """
        Simplified boolean check if a request is allowed.
        """
        return self.acquire(key, tokens=tokens).allowed
