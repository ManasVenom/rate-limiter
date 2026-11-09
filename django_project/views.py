"""
High-Performance API Views for Django Server.
Pre-encodes static JSON payloads into UTF-8 bytes to maximize throughput.
"""

from django.http import HttpRequest, HttpResponse

_PING_PAYLOAD = b'{"status": "ok", "message": "pong"}'
_DATA_PAYLOAD = (
    b'{"status": "success", "data": {"service": "order-gateway", "version": "1.0.0", "items_count": 42}}'
)
_HEALTH_PAYLOAD = b'{"status": "healthy"}'


def ping_view(request: HttpRequest) -> HttpResponse:
    """Lightweight endpoint to test request throughput."""
    return HttpResponse(_PING_PAYLOAD, content_type="application/json")


def data_view(request: HttpRequest) -> HttpResponse:
    """Simulated API data endpoint."""
    return HttpResponse(_DATA_PAYLOAD, content_type="application/json")


def health_view(request: HttpRequest) -> HttpResponse:
    """Exempt health check endpoint."""
    return HttpResponse(_HEALTH_PAYLOAD, content_type="application/json")
