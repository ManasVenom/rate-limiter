"""
In-memory Token Bucket rate limiter implementation.
"""

from dataclasses import dataclass
import threading
import time
from typing import Callable, Dict, Optional

from ratelimiter.base import BaseRateLimiter, RateLimitResult


class _BucketState:
    __slots__ = ("tokens", "last_refill")

    def __init__(self, tokens: float, last_refill: float):
        self.tokens = tokens
        self.last_refill = last_refill


class TokenBucketLimiter(BaseRateLimiter):
    """
    Thread-safe in-memory Token Bucket rate limiter.
    
    The Token Bucket algorithm allows bursts of traffic up to `capacity`,
    while strictly enforcing a long-term average rate of `refill_rate` tokens/sec.
    
    Refills are computed lazily on each access:
        new_tokens = elapsed_seconds * refill_rate
        tokens = min(capacity, current_tokens + new_tokens)
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        clock: Optional[Callable[[], float]] = None,
    ):
        """
        Initialize the Token Bucket Limiter.
        
        Args:
            capacity: Maximum burst capacity (maximum number of tokens the bucket can hold).
            refill_rate: Rate at which tokens are added per second.
            clock: Time provider returning seconds (defaults to `time.monotonic`).
                   Injectable for deterministic testing.
        """
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        if refill_rate <= 0:
            raise ValueError(f"refill_rate must be positive, got {refill_rate}")

        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._inv_refill_rate = 1.0 / self.refill_rate
        self.clock = clock or time.monotonic
        
        self._buckets: Dict[str, _BucketState] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, tokens: int = 1) -> RateLimitResult:
        """
        Attempt to consume `tokens` from the bucket associated with `key`.
        Optimized with in-place state mutation and zero garbage allocation on existing keys.
        """
        if tokens <= 0:
            raise ValueError(f"tokens to acquire must be positive, got {tokens}")
        if tokens > self.capacity:
            # Requested tokens exceed maximum bucket capacity; can never succeed
            return RateLimitResult(
                allowed=False,
                remaining=0.0,
                retry_after=float("inf"),
                reset_after=0.0,
                limit=self.capacity,
            )

        now = self.clock()

        with self._lock:
            state = self._buckets.get(key)

            if state is None:
                # First time key is seen; starts full and instantiate slotted state once
                current_tokens = self.capacity
                state = _BucketState(current_tokens, now)
                self._buckets[key] = state
            else:
                elapsed = now - state.last_refill
                if elapsed > 0.0:
                    current_tokens = min(self.capacity, state.tokens + (elapsed * self.refill_rate))
                else:
                    current_tokens = state.tokens

            if current_tokens >= tokens:
                new_tokens = current_tokens - tokens
                state.tokens = new_tokens
                state.last_refill = now

                # Reset time: time until bucket returns to full capacity
                reset_after = (self.capacity - new_tokens) * self._inv_refill_rate
                return RateLimitResult(
                    allowed=True,
                    remaining=new_tokens,
                    retry_after=0.0,
                    reset_after=reset_after,
                    limit=self.capacity,
                )
            else:
                # Not enough tokens. Do not deduct tokens.
                state.tokens = current_tokens
                state.last_refill = now

                deficit = tokens - current_tokens
                retry_after = deficit * self._inv_refill_rate
                reset_after = (self.capacity - current_tokens) * self._inv_refill_rate

                return RateLimitResult(
                    allowed=False,
                    remaining=current_tokens,
                    retry_after=retry_after,
                    reset_after=reset_after,
                    limit=self.capacity,
                )

    def get_tokens(self, key: str) -> float:
        """
        Inspect current token count for a key without consuming tokens.
        """
        now = self.clock()
        with self._lock:
            state = self._buckets.get(key)
            if state is None:
                return self.capacity
            elapsed = max(0.0, now - state.last_refill)
            return min(self.capacity, state.tokens + (elapsed * self.refill_rate))

    def reset(self, key: Optional[str] = None) -> None:
        """
        Reset bucket for a given key or clear all buckets if key is None.
        """
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)

    def prune_stale_keys(self, max_idle_seconds: Optional[float] = None) -> int:
        """
        Remove keys that have reached full capacity and been idle.
        Prevents unbounded memory growth in long-running services.
        
        Args:
            max_idle_seconds: Threshold idle time. Defaults to time required
                              for a completely empty bucket to reach full capacity.
        Returns:
            Number of keys pruned.
        """
        if max_idle_seconds is None:
            max_idle_seconds = self.capacity / self.refill_rate

        now = self.clock()
        keys_to_remove = []

        with self._lock:
            for k, state in self._buckets.items():
                elapsed = now - state.last_refill
                if elapsed >= max_idle_seconds:
                    # Accrued tokens would be at capacity
                    keys_to_remove.append(k)

            for k in keys_to_remove:
                del self._buckets[k]

        return len(keys_to_remove)
