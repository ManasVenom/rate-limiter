"""
Tests for Django RateLimitMiddleware and Django-integrated performance benchmarks.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import time
import unittest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")

import django
django.setup()

from django.test import Client, RequestFactory
from ratelimiter.django_middleware import RateLimitMiddleware
from ratelimiter.token_bucket import TokenBucketLimiter
from django_project.wsgi import application


class TestDjangoRateLimiter(unittest.TestCase):

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()

    def test_basic_django_rate_limiting(self):
        """Verify that requests are allowed up to burst limit, then return 429."""
        # Use an isolated middleware instance for this test
        limiter = TokenBucketLimiter(capacity=3, refill_rate=1.0)
        
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("OK")

        middleware = RateLimitMiddleware(dummy_view, limiter=limiter)

        ip = "192.168.1.50"
        # 3 requests should succeed
        for i in range(3):
            req = self.factory.get("/api/ping", REMOTE_ADDR=ip)
            resp = middleware(req)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("X-RateLimit-Remaining", resp.headers)
            self.assertEqual(resp.headers["X-RateLimit-Remaining"], str(2 - i))

        # 4th request must receive HTTP 429 Too Many Requests
        req4 = self.factory.get("/api/ping", REMOTE_ADDR=ip)
        resp4 = middleware(req4)
        self.assertEqual(resp4.status_code, 429)
        self.assertIn("Retry-After", resp4.headers)
        self.assertIn(b"Too Many Requests", resp4.content)

    def test_ip_isolation_in_django(self):
        """Verify that one client IP exceeding quota does not block another client."""
        limiter = TokenBucketLimiter(capacity=2, refill_rate=1.0)

        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("OK")

        middleware = RateLimitMiddleware(dummy_view, limiter=limiter)

        # Exhaust IP A
        req_a1 = self.factory.get("/api/ping", REMOTE_ADDR="10.0.0.1")
        req_a2 = self.factory.get("/api/ping", REMOTE_ADDR="10.0.0.1")
        req_a3 = self.factory.get("/api/ping", REMOTE_ADDR="10.0.0.1")
        middleware(req_a1)
        middleware(req_a2)
        resp_a3 = middleware(req_a3)
        self.assertEqual(resp_a3.status_code, 429)

        # IP B should still be allowed
        req_b1 = self.factory.get("/api/ping", REMOTE_ADDR="10.0.0.2")
        resp_b1 = middleware(req_b1)
        self.assertEqual(resp_b1.status_code, 200)

    def test_exempt_path(self):
        """Verify exempt endpoints like health checks bypass rate limiting."""
        limiter = TokenBucketLimiter(capacity=1, refill_rate=1.0)

        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("OK")

        middleware = RateLimitMiddleware(
            dummy_view, limiter=limiter, exempt_paths=["/healthz"]
        )

        # Multiple requests to exempt path
        for _ in range(5):
            req = self.factory.get("/healthz", REMOTE_ADDR="10.0.0.99")
            resp = middleware(req)
            self.assertEqual(resp.status_code, 200)

        # Tokens were untouched, so non-exempt endpoint can still be accessed
        req_ping = self.factory.get("/api/ping", REMOTE_ADDR="10.0.0.99")
        resp_ping = middleware(req_ping)
        self.assertEqual(resp_ping.status_code, 200)

    def test_django_wsgi_pipeline_latency(self):
        """
        Benchmark Django's full WSGI application pipeline (Routing, Middleware, View).
        Measures request latency through Django + Rate Limiter.
        """
        import io
        environ_template = {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/api/ping",
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "8000",
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(b""),
            "wsgi.errors": io.StringIO(),
            "wsgi.multithread": True,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
        }

        num_requests = 10_000
        latencies = []

        def noop_start_response(status, headers):
            pass

        start_time = time.perf_counter()
        for i in range(num_requests):
            env = environ_template.copy()
            # Distribute across client IPs
            env["REMOTE_ADDR"] = f"10.0.{i // 256}.{i % 256}"
            t0 = time.perf_counter()
            response_iter = application(env, noop_start_response)
            # Consume WSGI response body
            list(response_iter)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)

        total_time = time.perf_counter() - start_time
        rps = num_requests / total_time

        sorted_ms = sorted(lat * 1000.0 for lat in latencies)
        p50 = sorted_ms[int(num_requests * 0.50)]
        p95 = sorted_ms[int(num_requests * 0.95)]
        p99 = sorted_ms[int(num_requests * 0.99)]
        avg = sum(sorted_ms) / num_requests

        print(
            f"\n[Django WSGI Pipeline Benchmark (10,000 requests)]\n"
            f"  Total Time: {total_time:.4f}s | Throughput: {rps:,.0f} req/s\n"
            f"  Latency (ms): Avg={avg:.4f}ms, p50={p50:.4f}ms, "
            f"p95={p95:.4f}ms, p99={p99:.4f}ms"
        )

        # Assert throughput >= 10,000 req/s on single worker WSGI pipeline
        self.assertGreaterEqual(
            rps,
            10_000,
            f"Django single-worker throughput ({rps:,.0f} req/s) did not reach 10,000 req/s target!",
        )

        # Assert sub-5ms latency across Django + Rate Limiter
        self.assertLess(
            p99,
            5.0,
            f"Django p99 latency ({p99:.4f}ms) exceeded 5.0ms target!",
        )

    def test_django_asgi_dual_mode_support(self):
        """Verify that RateLimitMiddleware works natively in asynchronous ASGI mode."""
        import asyncio
        from django.http import HttpResponse

        limiter = TokenBucketLimiter(capacity=2, refill_rate=1.0)

        async def dummy_async_view(request):
            return HttpResponse(b"async ok", content_type="text/plain")

        middleware = RateLimitMiddleware(dummy_async_view, limiter=limiter)
        self.assertTrue(middleware._is_async)

        async def run_requests():
            req1 = self.factory.get("/api/ping", REMOTE_ADDR="192.168.1.88")
            resp1 = await middleware(req1)
            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp1.content, b"async ok")
            self.assertEqual(resp1.headers["X-RateLimit-Remaining"], "1")

            req2 = self.factory.get("/api/ping", REMOTE_ADDR="192.168.1.88")
            resp2 = await middleware(req2)
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.headers["X-RateLimit-Remaining"], "0")

            req3 = self.factory.get("/api/ping", REMOTE_ADDR="192.168.1.88")
            resp3 = await middleware(req3)
            self.assertEqual(resp3.status_code, 429)
            self.assertIn("Retry-After", resp3.headers)

        asyncio.run(run_requests())

    def test_django_wsgi_multiprocess_10k_throughput_and_sub_5ms_latency(self):
        """
        Validate multi-worker Django throughput and sub-5ms latency.
        Pre-warms the worker pool (standard production pre-fork model in Gunicorn/Uvicorn)
        and measures steady-state throughput and request latency.
        """
        from benchmarks.benchmark_django import _worker_process_batch
        from concurrent.futures import ProcessPoolExecutor

        total_requests = 20_000
        num_workers = 4
        per_worker = total_requests // num_workers

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            # Pre-fork / warm-up worker processes (reflecting production running server)
            list(executor.map(abs, range(num_workers)))

            start_time = time.perf_counter()
            futures = [
                executor.submit(_worker_process_batch, per_worker, w, False)
                for w in range(num_workers)
            ]
            all_latencies = []
            for f in futures:
                _, _, lats = f.result()
                all_latencies.extend(lats)
            total_time = time.perf_counter() - start_time

        rps = total_requests / total_time
        sorted_ms = sorted(lat * 1000.0 for lat in all_latencies)
        p99 = sorted_ms[int(len(sorted_ms) * 0.99)]

        print(
            f"\n[Django 4-Worker Cluster Benchmark (Pre-Forked)]\n"
            f"  Throughput: {rps:,.0f} req/s | p99: {p99:.4f}ms | Total Time: {total_time:.4f}s"
        )

        self.assertGreaterEqual(
            rps,
            10_000,
            f"Throughput {rps:.0f} req/s did not reach 10,000 req/s target",
        )
        self.assertLess(
            p99,
            5.0,
            f"p99 latency ({p99:.4f}ms) exceeded 5.0ms target",
        )


if __name__ == "__main__":
    unittest.main()
