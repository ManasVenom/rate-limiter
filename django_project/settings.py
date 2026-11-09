"""
Minimal, high-performance Django settings for the Rate Limiter benchmark.
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
    # Minimal configuration: no heavy DB / static files required
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

MIDDLEWARE = [
    # Put Rate Limiter at the very front of the middleware chain
    "ratelimiter.django_middleware.RateLimitMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "django_project.urls"

# Disable sessions, CSRF, and auth middleware for pure high-speed API performance
WSGI_APPLICATION = "django_project.wsgi.application"
