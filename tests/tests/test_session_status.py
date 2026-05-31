"""Tests for the session status endpoint."""

from __future__ import annotations

from django.utils import timezone
from rest_framework.test import APIClient

from edc_retinopathy.constants import REPORT_TYPE_COMBINED, REPORT_TYPE_PER_EYE
from edc_retinopathy.models import SessionFile

from .mixins import RetinopathyTestCaseMixin


class SessionStatusTests(RetinopathyTestCaseMixin):
    """Tests for GET /api/retinopathy/<subject_identifier>/status/"""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.url = "/api/retinopathy/105-10-0001-2/status/"

    def test_status_no_session(self) -> None:
        """Returns 404 when no session exists."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_status_empty_session_combined(self) -> None:
        """Returns session with no uploads (combined report_type)."""
        camera_session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_COMBINED,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["camera_session_id"]), str(camera_session.pk))
        self.assertEqual(response.data["uploaded"], [])
        self.assertEqual(
            sorted(response.data["missing"]),
            ["left", "report", "right"],
        )
        self.assertFalse(response.data["complete"])

    def test_status_empty_session_per_eye(self) -> None:
        """Returns session with no uploads (per_eye report_type)."""
        camera_session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_PER_EYE,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["camera_session_id"]), str(camera_session.pk))
        self.assertEqual(
            sorted(response.data["missing"]),
            ["left", "left_report", "right", "right_report"],
        )

    def test_status_partial_uploads(self) -> None:
        """Returns correct uploaded/missing after partial uploads."""
        camera_session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_COMBINED,
        )
        SessionFile.objects.create(
            camera_session=camera_session,
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
            sorted(response.data["missing"]),
            ["report", "right"],
        )
        self.assertFalse(response.data["complete"])

    def test_status_complete_session_combined(self) -> None:
        """Returns complete=True when all combined file types uploaded."""
        camera_session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_COMBINED,
        )
        for ft, fn in [
            ("left", "l.jpg"),
            ("right", "r.jpg"),
            ("report", "report.html"),
        ]:
            SessionFile.objects.create(
                camera_session=camera_session,
                file_type=ft,
                original_filename=fn,
                stored_filename=f"{ft}_stored.ext",
                file_size=1024,
                capture_datetime=timezone.now(),
            )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.data["uploaded"]),
            ["left", "report", "right"],
        )
        self.assertEqual(response.data["missing"], [])
        self.assertTrue(response.data["complete"])

    def test_status_complete_session_per_eye(self) -> None:
        """Returns complete=True when all per_eye file types uploaded."""
        camera_session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_PER_EYE,
        )
        for ft, fn in [
            ("left", "l.jpg"),
            ("right", "r.jpg"),
            ("left_report", "l_report.html"),
            ("right_report", "r_report.html"),
        ]:
            SessionFile.objects.create(
                camera_session=camera_session,
                file_type=ft,
                original_filename=fn,
                stored_filename=f"{ft}_stored.ext",
                file_size=1024,
                capture_datetime=timezone.now(),
            )
        response = self.client.get(self.url)
        self.assertTrue(response.data["complete"])

    def test_status_uses_most_recent_session(self) -> None:
        """Returns the most recent session, not an older one."""
        self.create_camera_session(self.rs)
        newer = self.create_camera_session(self.rs)
        response = self.client.get(self.url)
        self.assertEqual(str(response.data["camera_session_id"]), str(newer.pk))
        self.assertEqual(response.data["uploaded"], [])

    def test_status_unauthenticated(self) -> None:
        """Unauthenticated request returns 401."""
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_status_includes_report_datetime(self) -> None:
        """Response includes report_datetime as ISO string."""
        self.create_camera_session(self.rs)
        response = self.client.get(self.url)
        self.assertIn("report_datetime", response.data)
        self.assertIn("T", response.data["report_datetime"])
