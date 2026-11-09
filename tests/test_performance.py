"""
High-throughput and latency performance test suite.
Validates capability of handling 10,000+ requests/sec with sub-5ms latency.
"""

from concurrent.futures import ThreadPoolExecutor
import random
import time
import unittest

from ratelimiter.token_bucket import TokenBucketLimiter


class TestPerformanceThroughputAndLatency(unittest.TestCase):
    """Performance and latency benchmark tests."""

    TARGET_RPS = 10_000
    TARGET_LATENCY_MS = 5.0  # Max acceptable p99 latency in ms

    def setUp(self):
        # Configure generous capacity and refill to benchmark overhead of the limiter itself
        self.limiter = TokenBucketLimiter(capacity=100_000, refill_rate=50_000.0)

    def _calculate_percentiles(self, latencies_sec):
        sorted_latencies_ms = sorted(lat * 1000.0 for lat in latencies_sec)
        n = len(sorted_latencies_ms)
        p50 = sorted_latencies_ms[int(n * 0.50)]
        p95 = sorted_latencies_ms[int(n * 0.95)]
        p99 = sorted_latencies_ms[int(n * 0.99)]
        max_lat = sorted_latencies_ms[-1]
        avg_lat = sum(sorted_latencies_ms) / n
        return avg_lat, p50, p95, p99, max_lat

    def test_single_thread_10k_throughput_and_sub_5ms_latency(self):
        """
        Validate single-thread performance:
        Execute 10,000 requests sequentially.
        Verify throughput exceeds 10,000 req/s and p99 latency is well under 5ms.
        """
        count = 10_000
        latencies = []

        start_time = time.perf_counter()
        for _ in range(count):
            t0 = time.perf_counter()
            self.limiter.acquire("single-thread-client")
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        total_time = time.perf_counter() - start_time

        rps = count / total_time
        avg_lat, p50, p95, p99, max_lat = self._calculate_percentiles(latencies)

        print(
            f"\n[Single-Thread 10k Benchmark]\n"
            f"  Total Time: {total_time:.4f}s | Throughput: {rps:,.0f} req/s\n"
            f"  Latency (ms): Avg={avg_lat:.4f}ms, p50={p50:.4f}ms, "
            f"p95={p95:.4f}ms, p99={p99:.4f}ms, Max={max_lat:.4f}ms"
        )

        self.assertGreaterEqual(
            rps,
            self.TARGET_RPS,
            f"RPS {rps:.0f} was below target {self.TARGET_RPS}",
        )
        self.assertLess(
            p99,
            self.TARGET_LATENCY_MS,
            f"p99 latency {p99:.4f}ms exceeded target {self.TARGET_LATENCY_MS}ms",
        )

    def test_multithreaded_high_concurrency_shared_key(self):
        """
        Validate multi-threaded high-concurrency performance:
        16 concurrent worker threads hammering the exact same key for 10,000 requests total.
        Stress-tests lock contention under high-concurrency traffic spikes.
        """
        total_requests = 10_000
        num_workers = 16
        per_worker = total_requests // num_workers

        def worker():
            local_latencies = []
            for _ in range(per_worker):
                t0 = time.perf_counter()
                self.limiter.acquire("shared-concurrency-key")
                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)
            return local_latencies

        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker) for _ in range(num_workers)]
            all_latencies = []
            for f in futures:
                all_latencies.extend(f.result())
        total_time = time.perf_counter() - start_time

        rps = len(all_latencies) / total_time
        avg_lat, p50, p95, p99, max_lat = self._calculate_percentiles(all_latencies)

        print(
            f"\n[Multi-Thread Shared Key (16 Threads) Benchmark]\n"
            f"  Total Requests: {len(all_latencies)} in {total_time:.4f}s | Throughput: {rps:,.0f} req/s\n"
            f"  Latency (ms): Avg={avg_lat:.4f}ms, p50={p50:.4f}ms, "
            f"p95={p95:.4f}ms, p99={p99:.4f}ms, Max={max_lat:.4f}ms"
        )

        self.assertGreaterEqual(rps, self.TARGET_RPS)
        self.assertLess(p99, self.TARGET_LATENCY_MS)

    def test_microservice_gateway_traffic_1000_distinct_keys(self):
        """
        Simulate realistic microservice API gateway traffic:
        20,000 requests distributed across 1,000 distinct client IPs/API keys
        using 16 concurrent threads.
        """
        total_requests = 20_000
        num_workers = 16
        keys = [f"client-ip-10.0.{i // 256}.{i % 256}" for i in range(1000)]
        per_worker = total_requests // num_workers

        def worker():
            local_latencies = []
            for _ in range(per_worker):
                key = random.choice(keys)
                t0 = time.perf_counter()
                self.limiter.acquire(key)
                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)
            return local_latencies

        start_time = time.perf_counter()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker) for _ in range(num_workers)]
            all_latencies = []
            for f in futures:
                all_latencies.extend(f.result())
        total_time = time.perf_counter() - start_time

        rps = len(all_latencies) / total_time
        avg_lat, p50, p95, p99, max_lat = self._calculate_percentiles(all_latencies)

        print(
            f"\n[Microservice Gateway (1,000 Keys, 16 Threads) Benchmark]\n"
            f"  Total Requests: {len(all_latencies)} in {total_time:.4f}s | Throughput: {rps:,.0f} req/s\n"
            f"  Latency (ms): Avg={avg_lat:.4f}ms, p50={p50:.4f}ms, "
            f"p95={p95:.4f}ms, p99={p99:.4f}ms, Max={max_lat:.4f}ms"
        )

        self.assertGreaterEqual(rps, self.TARGET_RPS)
        self.assertLess(p99, self.TARGET_LATENCY_MS)


if __name__ == "__main__":
    unittest.main()
