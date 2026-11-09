"""
API Views for Django Server.
"""

from django.http import HttpRequest, JsonResponse


def ping_view(request: HttpRequest) -> JsonResponse:
    """Lightweight endpoint to test request throughput."""
    return JsonResponse({"status": "ok", "message": "pong"})


def data_view(request: HttpRequest) -> JsonResponse:
    """Simulated API data endpoint."""
    return JsonResponse({
        "status": "success",
        "data": {
            "service": "order-gateway",
            "version": "1.0.0",
            "items_count": 42,
        }
    })


def health_view(request: HttpRequest) -> JsonResponse:
    """Exempt health check endpoint."""
    return JsonResponse({"status": "healthy"})
