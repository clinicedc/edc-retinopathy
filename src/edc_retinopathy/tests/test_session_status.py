"""Tests for the session status endpoint."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import RetinalImage, RetinopathySession
from .models import RegisteredSubject


class SessionStatusTests(TestCase):
    """Tests for GET /api/retinopathy/<subject_identifier>/status/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(username="camera", password="pw")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.rs = RegisteredSubject.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            gender="M",
            dob=date(1990, 6, 15),
        )
        self.url = "/api/retinopathy/105-10-0001-2/status/"

    def test_status_no_session(self) -> None:
        """Returns 404 when no session exists."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_status_empty_session(self) -> None:
        """Returns session with no uploads."""
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["session_id"], session.pk)
        self.assertEqual(response.data["uploaded"], [])
        self.assertEqual(
            sorted(response.data["missing"]), ["left", "report", "right"]
        )
        self.assertFalse(response.data["complete"])

    def test_status_partial_uploads(self) -> None:
        """Returns correct uploaded/missing after partial uploads."""
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        RetinalImage.objects.create(
            session=session,
            file_type="left",
            original_filename="left.jpg",
            stored_filename="abc123.jpg",
            file_size=1024,
            capture_datetime=timezone.now(),
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uploaded"], ["left"])
        self.assertEqual(
            sorted(response.data["missing"]), ["report", "right"]
        )
        self.assertFalse(response.data["complete"])

    def test_status_complete_session(self) -> None:
        """Returns complete=True when all three files uploaded."""
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        for ft, fn in [
            ("left", "l.jpg"),
            ("right", "r.jpg"),
            ("report", "rpt.pdf"),
        ]:
            RetinalImage.objects.create(
                session=session,
                file_type=ft,
                original_filename=fn,
                stored_filename=f"{ft}_stored.ext",
                file_size=1024,
                capture_datetime=timezone.now(),
            )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.data["uploaded"]), ["left", "report", "right"]
        )
        self.assertEqual(response.data["missing"], [])
        self.assertTrue(response.data["complete"])

    def test_status_uses_most_recent_session(self) -> None:
        """Returns the most recent session, not an older one."""
        older = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        RetinalImage.objects.create(
            session=older,
            file_type="left",
            original_filename="l.jpg",
            stored_filename="old_stored.jpg",
            file_size=1024,
            capture_datetime=timezone.now(),
        )
        newer = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data["session_id"], newer.pk)
        self.assertEqual(response.data["uploaded"], [])

    def test_status_unauthenticated(self) -> None:
        """Unauthenticated request returns 401."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_status_includes_created_datetime(self) -> None:
        """Response includes created_datetime as ISO string."""
        RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
        )
        response = self.client.get(self.url)
        self.assertIn("created_datetime", response.data)
        self.assertIn("T", response.data["created_datetime"])
