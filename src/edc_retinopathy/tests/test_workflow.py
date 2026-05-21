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

from ..models import RetinalImage, RetinopathySession
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
        """Step 1: resolve, Step 2: left, Step 3: right, Step 4: report."""
        # Step 0: Ping
        response = self.client.get("/api/retinopathy/ping/")
        self.assertEqual(response.status_code, 200)

        # Step 1: Resolve
        resolve_data = self._resolve()
        session_id = resolve_data["session_id"]

        self.assertEqual(RetinopathySession.objects.count(), 1)
        session = RetinopathySession.objects.get(pk=session_id)
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

        # Step 4: Report
        report_data = self._upload("report")
        self.assertEqual(report_data["session_id"], session_id)
        self.assertEqual(report_data["file_type"], "report")

        # Verify final state
        self.assertEqual(RetinalImage.objects.count(), 3)
        self.assertEqual(session.files.count(), 3)

        file_types = set(session.files.values_list("file_type", flat=True))
        self.assertEqual(file_types, {"left", "right", "report"})

        # Verify all files exist on disk
        storage = Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images"
        for img in RetinalImage.objects.all():
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
        s1 = RetinopathySession.objects.get(pk=session1_id)
        s2 = RetinopathySession.objects.get(pk=session2_id)
        self.assertEqual(s1.files.count(), 1)
        self.assertEqual(s2.files.count(), 1)

    def test_workflow_repeat_visit_new_session(self) -> None:
        """A second resolve creates a new session; uploads go to the latest."""
        # First visit
        r1 = self._resolve()
        session1_id = r1["session_id"]
        self._upload("left")

        # Second visit (new session)
        r2 = self._resolve()
        session2_id = r2["session_id"]
        self.assertNotEqual(session1_id, session2_id)

        # Upload left eye again — goes to session 2
        left_data = self._upload("left")
        self.assertEqual(left_data["session_id"], session2_id)

        # Session 1 has 1 file, session 2 has 1 file
        s1 = RetinopathySession.objects.get(pk=session1_id)
        s2 = RetinopathySession.objects.get(pk=session2_id)
        self.assertEqual(s1.files.count(), 1)
        self.assertEqual(s2.files.count(), 1)

    def test_workflow_retry_after_timeout(self) -> None:
        """Camera retries an upload after a network timeout; gets 200."""
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

        # Camera thinks it failed, retries
        f2 = SimpleUploadedFile(
            "left.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg"
        )
        resp2 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f2, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        # Gets 200 (not 409) with the existing record
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["id"], resp1.data["id"])

        # Only one file exists
        self.assertEqual(RetinalImage.objects.count(), 1)

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

        images = RetinalImage.objects.order_by("file_type")
        self.assertEqual(images.count(), 2)
        for img in images:
            self.assertIsNotNone(img.capture_datetime)
