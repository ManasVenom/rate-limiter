"""
Comprehensive unit tests for the Token Bucket Rate Limiter.
"""

from concurrent.futures import ThreadPoolExecutor
import unittest

from ratelimiter.base import RateLimitExceeded
from ratelimiter.decorator import rate_limit
from ratelimiter.token_bucket import TokenBucketLimiter


class MockClock:
    """Controllable clock for deterministic time testing."""

    def __init__(self, start_time: float = 1000.0):
        self._time = start_time

    def __call__(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds


class TestTokenBucketLimiter(unittest.TestCase):

    def setUp(self):
        self.clock = MockClock()
        # 5 tokens max burst, 2 tokens refilled per second
        self.limiter = TokenBucketLimiter(capacity=5, refill_rate=2.0, clock=self.clock)

    def test_burst_up_to_capacity(self):
        """Verify that requests up to capacity succeed immediately."""
        key = "client-1"
        for i in range(5):
            res = self.limiter.acquire(key, tokens=1)
            self.assertTrue(res.allowed, f"Request {i+1} should be allowed")
            self.assertEqual(res.remaining, 4 - i)

        # 6th request must be rejected because bucket is exhausted
        res_fail = self.limiter.acquire(key, tokens=1)
        self.assertFalse(res_fail.allowed)
        self.assertEqual(res_fail.remaining, 0.0)
        self.assertAlmostEqual(res_fail.retry_after, 0.5)  # 1 token needed / 2 tokens per sec = 0.5s

    def test_refill_mechanic(self):
        """Verify that tokens replenish proportionally to elapsed time."""
        key = "client-2"
        # Consume all 5 tokens
        for _ in range(5):
            self.limiter.acquire(key)

        self.assertFalse(self.limiter.is_allowed(key))

        # Advance 1.0 second -> replenishes 2 tokens
        self.clock.advance(1.0)
        self.assertAlmostEqual(self.limiter.get_tokens(key), 2.0)

        # Should be able to consume 2 tokens
        self.assertTrue(self.limiter.acquire(key, tokens=2).allowed)
        self.assertFalse(self.limiter.acquire(key, tokens=1).allowed)

        # Advance 10 seconds -> should cap at max capacity (5), not overflow
        self.clock.advance(10.0)
        self.assertEqual(self.limiter.get_tokens(key), 5.0)

    def test_per_key_isolation(self):
        """Verify that limits for different keys are completely independent."""
        # Exhaust user-A
        for _ in range(5):
            self.limiter.acquire("user-A")
        self.assertFalse(self.limiter.is_allowed("user-A"))

        # user-B should still have full quota
        self.assertTrue(self.limiter.is_allowed("user-B"))
        self.assertEqual(self.limiter.get_tokens("user-B"), 4.0)

    def test_oversized_request(self):
        """Verify request exceeding max capacity is rejected."""
        res = self.limiter.acquire("client-oversize", tokens=10)
        self.assertFalse(res.allowed)
        self.assertEqual(res.retry_after, float("inf"))

    def test_http_headers_generation(self):
        """Verify RFC-compatible rate limiting headers."""
        res = self.limiter.acquire("client-headers", tokens=2)
        self.assertTrue(res.allowed)
        headers = res.to_headers()
        self.assertEqual(headers["X-RateLimit-Limit"], "5")
        self.assertEqual(headers["X-RateLimit-Remaining"], "3")
        self.assertIn("X-RateLimit-Reset", headers)
        self.assertNotIn("Retry-After", headers)

        # Exhaust remainder and test Retry-After
        self.limiter.acquire("client-headers", tokens=3)
        res_blocked = self.limiter.acquire("client-headers", tokens=1)
        headers_blocked = res_blocked.to_headers()
        self.assertIn("Retry-After", headers_blocked)

    def test_decorator_enforcement(self):
        """Verify the @rate_limit decorator."""
        clock = MockClock()
        limiter = TokenBucketLimiter(capacity=2, refill_rate=1.0, clock=clock)

        call_count = 0

        @rate_limit(limiter, key=lambda user: user)
        def target_api(user: str):
            nonlocal call_count
            call_count += 1
            return f"ok-{user}"

        self.assertEqual(target_api("alice"), "ok-alice")
        self.assertEqual(target_api("alice"), "ok-alice")
        self.assertEqual(call_count, 2)

        # 3rd call exceeds limit
        with self.assertRaises(RateLimitExceeded):
            target_api("alice")

        # Custom handler test
        fallback_invoked = False

        def custom_fallback(result, *args, **kwargs):
            nonlocal fallback_invoked
            fallback_invoked = True
            return "throttled"

        @rate_limit(limiter, key="static-key", on_limit_exceeded=custom_fallback)
        def sensitive_task():
            return "done"

        sensitive_task()
        sensitive_task()
        result = sensitive_task()
        self.assertTrue(fallback_invoked)
        self.assertEqual(result, "throttled")

    def test_multithreaded_concurrency(self):
        """Verify thread-safety when multiple threads acquire tokens concurrently."""
        real_limiter = TokenBucketLimiter(capacity=100, refill_rate=10.0)
        key = "concurrent-user"
        total_attempts = 150

        results = []

        def worker():
            res = real_limiter.acquire(key, tokens=1)
            results.append(res.allowed)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(total_attempts)]
            for f in futures:
                f.result()

        # Exactly 100 should be allowed (burst), the remaining 50 should be blocked
        allowed_count = sum(1 for r in results if r is True)
        self.assertEqual(allowed_count, 100)
        self.assertEqual(len(results), 150)

    def test_stale_key_pruning(self):
        """Verify memory cleanup of idle keys."""
        self.limiter.acquire("stale-1")
        self.limiter.acquire("stale-2")

        # Before idle threshold, pruning should do nothing
        pruned = self.limiter.prune_stale_keys(max_idle_seconds=10.0)
        self.assertEqual(pruned, 0)

        # Advance past threshold
        self.clock.advance(15.0)
        pruned = self.limiter.prune_stale_keys(max_idle_seconds=10.0)
        self.assertEqual(pruned, 2)
        # Buckets are cleaned from memory
        self.assertEqual(len(self.limiter._buckets), 0)


if __name__ == "__main__":
    unittest.main()
