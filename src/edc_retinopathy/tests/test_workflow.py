"""End-to-end workflow tests simulating the camera's four-step protocol."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import CameraSession, SessionFile
from .models import RegisteredSubject

CAPTURE_DT = "2026-05-21T10:30:00Z"


class FullWorkflowTests(TestCase):
    """Simulate the camera's complete four-step protocol."""

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

    def _resolve(self) -> dict:
        response = self.client.post(
            "/api/retinopathy/resolve/",
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": date.today().year - 1990,
                "device_id": "CAM-001",
                "site_id": "SITE-A",
            },
            format="json",
        )
        return response.data

    def _upload(self, file_type: str, capture_dt: str = CAPTURE_DT) -> dict:
        if file_type == "report":
            f = SimpleUploadedFile(
                name="report.pdf",
                content=b"%PDF-1.4" + b"\x00" * 200,
                content_type="application/pdf",
            )
        elif file_type in ("left_report", "right_report"):
            f = SimpleUploadedFile(
                name=f"{file_type}.html",
                content=b"<!DOCTYPE html><html><body>Report</body></html>",
                content_type="text/html",
            )
        else:
            f = SimpleUploadedFile(
                name=f"{file_type}_eye.jpg",
                content=b"\xff\xd8\xff\xe0" + b"\x00" * 200,
                content_type="image/jpeg",
            )
        response = self.client.post(
            f"/api/retinopathy/105-10-0001-2/{file_type}/",
            {"file": f, "capture_datetime": capture_dt},
            format="multipart",
        )
        return response.data

    def test_full_workflow(self) -> None:
        """Resolve, upload left, right, left_report, right_report."""
        # Step 0: Ping
        response = self.client.get("/api/retinopathy/ping/")
        self.assertEqual(response.status_code, 200)

        # Step 1: Resolve
        resolve_data = self._resolve()
        session_id = resolve_data["session_id"]

        self.assertEqual(CameraSession.objects.count(), 1)
        session = CameraSession.objects.get(pk=session_id)
        self.assertEqual(session.subject_identifier, "105-10-0001-2")
        self.assertEqual(session.device_id, "CAM-001")

        # Step 2: Left eye
        left_data = self._upload("left")
        self.assertEqual(left_data["session_id"], session_id)
        self.assertEqual(left_data["file_type"], "left")

        # Check status mid-workflow
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/"
        )
        self.assertEqual(status_resp.data["uploaded"], ["left"])
        self.assertFalse(status_resp.data["complete"])

        # Step 3: Right eye
        right_data = self._upload("right")
        self.assertEqual(right_data["session_id"], session_id)
        self.assertEqual(right_data["file_type"], "right")

        # Step 4: Left eye report
        left_report_data = self._upload("left_report")
        self.assertEqual(left_report_data["session_id"], session_id)
        self.assertEqual(left_report_data["file_type"], "left_report")

        # Step 5: Right eye report
        right_report_data = self._upload("right_report")
        self.assertEqual(right_report_data["session_id"], session_id)
        self.assertEqual(right_report_data["file_type"], "right_report")

        # Verify final state
        self.assertEqual(SessionFile.objects.count(), 4)
        self.assertEqual(session.files.count(), 4)

        file_types = set(session.files.values_list("file_type", flat=True))
        self.assertEqual(
            file_types, {"left", "right", "left_report", "right_report"}
        )

        # Verify all files exist on disk
        storage = Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images"
        for img in SessionFile.objects.all():
            self.assertTrue((storage / img.stored_filename).exists())

        # Status shows complete
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/"
        )
        self.assertTrue(status_resp.data["complete"])

    def test_workflow_two_subjects_interleaved(self) -> None:
        """Two subjects uploading concurrently don't cross-link."""
        RegisteredSubject.objects.create(
            subject_identifier="105-10-0002-3",
            initials="AB",
            gender="F",
            dob=date(1985, 1, 1),
        )

        # Resolve both subjects
        r1 = self.client.post(
            "/api/retinopathy/resolve/",
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        r2 = self.client.post(
            "/api/retinopathy/resolve/",
            {
                "subject_identifier": "105-10-0002-3",
                "initials": "AB",
                "sex": "F",
            },
            format="json",
        )
        session1_id = r1.data["session_id"]
        session2_id = r2.data["session_id"]
        self.assertNotEqual(session1_id, session2_id)

        # Upload left eye for both
        f1 = SimpleUploadedFile(
            "left.jpg", b"\xff\xd8\xff" + b"\x00" * 50, "image/jpeg"
        )
        f2 = SimpleUploadedFile(
            "left.jpg", b"\xff\xd8\xff" + b"\x00" * 50, "image/jpeg"
        )

        resp1 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f1, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        resp2 = self.client.post(
            "/api/retinopathy/105-10-0002-3/left/",
            {"file": f2, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )

        self.assertEqual(resp1.data["session_id"], session1_id)
        self.assertEqual(resp2.data["session_id"], session2_id)

        # Each session has exactly one file
        s1 = CameraSession.objects.get(pk=session1_id)
        s2 = CameraSession.objects.get(pk=session2_id)
        self.assertEqual(s1.files.count(), 1)
        self.assertEqual(s2.files.count(), 1)

    def test_workflow_repeat_visit_new_session(self) -> None:
        """After completing a session, a new resolve creates a new session."""
        # First visit — complete it
        r1 = self._resolve()
        session1_id = r1["session_id"]
        self._upload("left")
        self._upload("right")
        self._upload("left_report")
        self._upload("right_report")

        # Second visit — new session since first is complete
        r2 = self._resolve()
        session2_id = r2["session_id"]
        self.assertNotEqual(session1_id, session2_id)
        self.assertFalse(r2.get("reactivated", False))

        # Upload left eye — goes to session 2
        left_data = self._upload("left")
        self.assertEqual(left_data["session_id"], session2_id)

    def test_workflow_reactivation_after_disconnect(self) -> None:
        """Camera disconnects mid-workflow, reconnects, and resumes."""
        # Resolve and upload left eye
        r1 = self._resolve()
        session_id = r1["session_id"]
        self._upload("left")

        # Camera disconnects ... reconnects and resolves again
        r2 = self._resolve()
        self.assertEqual(r2["session_id"], session_id)
        self.assertTrue(r2["reactivated"])

        # Check status to see what's done
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/"
        )
        self.assertEqual(status_resp.data["uploaded"], ["left"])

        # Continue with remaining uploads
        self._upload("right")
        self._upload("left_report")
        self._upload("right_report")

        # Session is now complete
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/"
        )
        self.assertTrue(status_resp.data["complete"])

    def test_workflow_retry_after_timeout(self) -> None:
        """Camera retries an upload after a network timeout; replaces."""
        self._resolve()

        # First upload succeeds
        f1 = SimpleUploadedFile(
            "left.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg"
        )
        resp1 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f1, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(resp1.status_code, 201)

        # Camera thinks it failed, retries with same capture_datetime
        f2 = SimpleUploadedFile(
            "left.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg"
        )
        resp2 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f2, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        # Replacement — new record, 201
        self.assertEqual(resp2.status_code, 201)
        self.assertNotEqual(resp2.data["id"], resp1.data["id"])

        # Only one file exists (old was replaced)
        self.assertEqual(SessionFile.objects.count(), 1)

    def test_workflow_with_capture_datetime(self) -> None:
        """Full workflow with distinct capture_datetime on each image."""
        self._resolve()

        for file_type, dt in [
            ("left", "2026-05-21T10:30:00Z"),
            ("right", "2026-05-21T10:31:00Z"),
        ]:
            f = SimpleUploadedFile(
                f"{file_type}.jpg",
                b"\xff\xd8\xff" + b"\x00" * 100,
                "image/jpeg",
            )
            response = self.client.post(
                f"/api/retinopathy/105-10-0001-2/{file_type}/",
                {"file": f, "capture_datetime": dt},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201)

        images = SessionFile.objects.order_by("file_type")
        self.assertEqual(images.count(), 2)
        for img in images:
            self.assertIsNotNone(img.capture_datetime)
