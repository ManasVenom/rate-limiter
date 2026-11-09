"""
Standalone High-Throughput & Latency Benchmark Script.
Simulates high-concurrency traffic spikes to verify 10,000+ req/s and sub-5ms latency.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import random
import sys
import time
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ratelimiter import TokenBucketLimiter


def run_benchmark(
    name: str,
    total_requests: int,
    num_threads: int,
    distinct_keys: int,
) -> Dict[str, float]:
    limiter = TokenBucketLimiter(capacity=200_000, refill_rate=100_000.0)
    keys = [f"client_{i}" for i in range(distinct_keys)]
    per_worker = total_requests // num_threads

    def worker(worker_id: int) -> List[float]:
        latencies = []
        rng = random.Random(worker_id)
        for _ in range(per_worker):
            key = keys[0] if distinct_keys == 1 else rng.choice(keys)
            t0 = time.perf_counter()
            limiter.acquire(key)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
        return latencies

    start_total = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = [pool.submit(worker, i) for i in range(num_threads)]
        all_latencies = []
        for f in futures:
            all_latencies.extend(f.result())
    elapsed = time.perf_counter() - start_total

    sorted_ms = sorted(lat * 1000.0 for lat in all_latencies)
    n = len(sorted_ms)

    return {
        "name": name,
        "total_requests": n,
        "elapsed_sec": elapsed,
        "rps": n / elapsed,
        "avg_ms": sum(sorted_ms) / n,
        "p50_ms": sorted_ms[int(n * 0.50)],
        "p90_ms": sorted_ms[int(n * 0.90)],
        "p95_ms": sorted_ms[int(n * 0.95)],
        "p99_ms": sorted_ms[int(n * 0.99)],
        "max_ms": sorted_ms[-1],
    }


def main():
    print("=" * 80)
    print("⚡ RATE LIMITER PERFORMANCE & LATENCY BENCHMARK")
    print("Target: 10,000+ requests/sec | Latency: < 5.0 ms")
    print("=" * 80)

    benchmarks = [
        ("Single Thread (1 key)", 10_000, 1, 1),
        ("Multi-Thread Contention (16 threads, 1 key)", 10_000, 16, 1),
        ("Gateway Traffic (16 threads, 1,000 keys)", 20_000, 16, 1_000),
        ("High-Volume Spike (32 threads, 5,000 keys)", 50_000, 32, 5_000),
    ]

    results = []
    for name, reqs, threads, keys in benchmarks:
        print(f"\nRunning: {name} ({reqs:,} reqs)...", flush=True)
        res = run_benchmark(name, reqs, threads, keys)
        results.append(res)

    print("\n" + "=" * 90)
    print(
        f"{'Benchmark Scenario':<36} {'Reqs':<8} {'RPS':<10} {'Avg(ms)':<9} {'p95(ms)':<9} {'p99(ms)':<9} {'Status'}"
    )
    print("-" * 90)

    for r in results:
        passed = (r["rps"] >= 10_000) and (r["p99_ms"] < 5.0)
        status_str = "✅ PASS" if passed else "❌ FAIL"
        print(
            f"{r['name']:<36} {r['total_requests']:<8} {r['rps']:<10,.0f} "
            f"{r['avg_ms']:<9.4f} {r['p95_ms']:<9.4f} {r['p99_ms']:<9.4f} {status_str}"
        )
    print("=" * 90)
    print("Summary:")
    print("  • Throughput Target : >= 10,000 req/sec")
    print("  • Latency Target    : < 5.0000 ms (p99)")
    print("=" * 90)


if __name__ == "__main__":
    main()
