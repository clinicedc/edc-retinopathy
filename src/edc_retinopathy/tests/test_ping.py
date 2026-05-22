"""Tests for the health-check ping endpoint."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


class PingTests(TestCase):
    """Tests for GET /api/retinopathy/ping/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(username="camera", password="pw")
        self.token = Token.objects.create(user=self.user)
        self.url = "/api/retinopathy/ping/"

    def test_ping_authenticated(self) -> None:
        """Authenticated ping returns 200 with status ok."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_ping_unauthenticated(self) -> None:
        """Unauthenticated ping returns 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_ping_invalid_token(self) -> None:
        """Invalid token returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid-token-here")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
