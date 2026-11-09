"""
Minimal, high-performance Django settings for the Rate Limiter project.
Optimized to handle 10,000+ requests/sec with sub-5ms latency.
"""

from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# Ensure rate-limiter root is in python path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SECRET_KEY = "django-insecure-rate-limiter-benchmark-key"
DEBUG = False
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
]

MIDDLEWARE = [
    # Put Rate Limiter at the very front of the middleware chain
    "ratelimiter.django_middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "django_project.urls"

# High-throughput API optimizations: disable internationalization, tz, and slash redirection
APPEND_SLASH = False
PREPEND_WWW = False
USE_I18N = False
USE_TZ = False

WSGI_APPLICATION = "django_project.wsgi.application"
ASGI_APPLICATION = "django_project.asgi.application"
