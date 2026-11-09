"""
URL configuration for django_project.
"""

from django.urls import path
from django_project import views

urlpatterns = [
    path("api/ping", views.ping_view, name="api-ping"),
    path("api/data", views.data_view, name="api-data"),
    path("healthz", views.health_view, name="healthz"),
]
