"""
Django Middleware for Rate Limiting.
"""

from typing import Callable, Iterable, Optional, Set
from django.http import HttpRequest, HttpResponse, JsonResponse

from ratelimiter.base import BaseRateLimiter, RateLimitResult
from ratelimiter.token_bucket import TokenBucketLimiter


def default_key_func(request: HttpRequest) -> str:
    """Extract client IP address as the default rate limit key."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "127.0.0.1")
    return f"ip:{ip}"


class RateLimitMiddleware:
    """
    Django middleware that enforces rate limiting on incoming HTTP requests.
    Attaches RFC-compliant rate limit headers and responds with HTTP 429
    when limits are exceeded.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
        limiter: Optional[BaseRateLimiter] = None,
        key_func: Optional[Callable[[HttpRequest], str]] = None,
        exempt_paths: Optional[Iterable[str]] = None,
    ):
        self.get_response = get_response
        self.limiter = limiter or TokenBucketLimiter(capacity=20_000, refill_rate=10_000.0)
        self.key_func = key_func or default_key_func
        self.exempt_paths: Set[str] = set(exempt_paths or ["/healthz", "/metrics", "/favicon.ico"])

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path in self.exempt_paths:
            return self.get_response(request)

        key = self.key_func(request)
        result: RateLimitResult = self.limiter.acquire(key)

        if not result.allowed:
            response = JsonResponse(
                {
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please retry later.",
                    "retry_after": round(result.retry_after, 3),
                },
                status=429,
            )
            for header, val in result.to_headers().items():
                response[header] = val
            return response

        response = self.get_response(request)

        # Attach rate limiting headers to successful responses
        for header, val in result.to_headers().items():
            response[header] = val

        return response
