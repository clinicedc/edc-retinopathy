"""Tests for the health-check ping endpoint."""

from __future__ import annotations

from rest_framework.test import APIClient

from .mixins import RetinopathyTestCaseMixin


class PingTests(RetinopathyTestCaseMixin):
    """Tests for GET /api/retinopathy/ping/"""

    def setUp(self) -> None:
        super().setUp()
        self.url = "/api/retinopathy/ping/"

    def test_ping_authenticated(self) -> None:
        """Authenticated ping returns 200 with status ok."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_ping_unauthenticated(self) -> None:
        """Unauthenticated ping returns 401."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_ping_invalid_token(self) -> None:
        """Invalid token returns 401."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token invalid-token-here")
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)
