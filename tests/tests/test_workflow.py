"""End-to-end workflow tests simulating the camera's protocol.

Flow: clinician creates CameraSession in EDC → camera resolves →
camera uploads files → status shows complete.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from edc_retinopathy.constants import REPORT_TYPE_COMBINED, REPORT_TYPE_PER_EYE
from edc_retinopathy.models import SessionFile

from .mixins import RetinopathyTestCaseMixin

CAPTURE_DT = "2026-05-21T10:30:00Z"


class FullWorkflowTests(RetinopathyTestCaseMixin):
    """Simulate the camera's complete protocol."""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()

    def _resolve(
        self,
        subject_identifier: str = "105-10-0001-2",
        initials: str = "JD",
        sex: str = "M",
        device_id: str = "CAM-001",
    ) -> dict:
        response = self.client.post(
            "/api/retinopathy/resolve/",
            {
                "subject_identifier": subject_identifier,
                "initials": initials,
                "sex": sex,
                "device_id": device_id,
            },
            format="json",
        )
        return response.data

    def _upload(
        self,
        subject_identifier: str,
        file_type: str,
        capture_dt: str = CAPTURE_DT,
    ) -> dict:
        if file_type in ("report", "left_report", "right_report"):
            f = SimpleUploadedFile(
                name=f"{file_type}.pdf",
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
            f"/api/retinopathy/{subject_identifier}/{file_type}/",
            {"file": f, "capture_datetime": capture_dt},
            format="multipart",
        )
        return response.data

    def test_full_workflow_combined(self) -> None:
        """Resolve, upload left, right, report for combined report type."""
        session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_COMBINED,
        )

        # Step 0: Ping
        response = self.client.get("/api/retinopathy/ping/")
        self.assertEqual(response.status_code, 200)

        # Step 1: Resolve
        resolve_data = self._resolve()
        self.assertEqual(resolve_data["camera_session_id"], session.pk)
        self.assertEqual(resolve_data["uploaded"], [])

        # Step 2: Left eye
        left_data = self._upload("105-10-0001-2", "left")
        self.assertEqual(str(left_data["camera_session_id"]), str(session.pk))
        self.assertEqual(left_data["file_type"], "left")

        # Check status mid-workflow
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/",
        )
        self.assertEqual(status_resp.data["uploaded"], ["left"])
        self.assertFalse(status_resp.data["complete"])

        # Step 3: Right eye
        right_data = self._upload("105-10-0001-2", "right")
        self.assertEqual(str(right_data["camera_session_id"]), str(session.pk))

        # Step 4: Report
        report_data = self._upload("105-10-0001-2", "report")
        self.assertEqual(str(report_data["camera_session_id"]), str(session.pk))

        # Verify final state
        self.assertEqual(SessionFile.objects.count(), 3)
        self.assertEqual(session.files.count(), 3)
        file_types = set(session.files.values_list("file_type", flat=True))
        self.assertEqual(file_types, {"left", "right", "report"})

        # Verify all files exist on disk
        storage = Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images"
        for sf in SessionFile.objects.all():
            self.assertTrue((storage / sf.stored_filename).exists())

        # Status shows complete
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/",
        )
        self.assertTrue(status_resp.data["complete"])

    def test_full_workflow_per_eye(self) -> None:
        """Resolve, upload left, right, left_report, right_report."""
        session = self.create_camera_session(
            self.rs,
            report_type=REPORT_TYPE_PER_EYE,
        )

        resolve_data = self._resolve()
        self.assertEqual(resolve_data["camera_session_id"], session.pk)

        for ft in ("left", "right", "left_report", "right_report"):
            data = self._upload("105-10-0001-2", ft)
            self.assertEqual(str(data["camera_session_id"]), str(session.pk))

        self.assertEqual(session.files.count(), 4)

        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/",
        )
        self.assertTrue(status_resp.data["complete"])

    def test_workflow_two_subjects_interleaved(self) -> None:
        """Two subjects uploading concurrently don't cross-link."""
        rs2 = self.create_registered_subject(
            subject_identifier="105-10-0002-3",
            initials="AB",
            gender="F",
        )
        session1 = self.create_camera_session(self.rs)
        session2 = self.create_camera_session(rs2)

        # Resolve both
        r1 = self._resolve("105-10-0001-2", "JD", "M")
        r2 = self._resolve("105-10-0002-3", "AB", "F")
        self.assertEqual(r1["camera_session_id"], session1.pk)
        self.assertEqual(r2["camera_session_id"], session2.pk)

        # Upload left eye for both
        d1 = self._upload("105-10-0001-2", "left")
        d2 = self._upload("105-10-0002-3", "left")
        self.assertEqual(str(d1["camera_session_id"]), str(session1.pk))
        self.assertEqual(str(d2["camera_session_id"]), str(session2.pk))

        # Each session has exactly one file
        self.assertEqual(session1.files.count(), 1)
        self.assertEqual(session2.files.count(), 1)

    def test_workflow_reactivation_after_disconnect(self) -> None:
        """Camera disconnects mid-workflow, reconnects, and resumes."""
        session = self.create_camera_session(self.rs)

        # Resolve and upload left eye
        self._resolve()
        self._upload("105-10-0001-2", "left")

        # Camera disconnects ... reconnects and resolves again
        r2 = self._resolve()
        self.assertEqual(r2["camera_session_id"], session.pk)
        self.assertIn("left", r2["uploaded"])

        # Check status shows what was already uploaded
        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/",
        )
        self.assertEqual(status_resp.data["uploaded"], ["left"])

        # Continue with remaining uploads
        self._upload("105-10-0001-2", "right")
        self._upload("105-10-0001-2", "report")

        status_resp = self.client.get(
            "/api/retinopathy/105-10-0001-2/status/",
        )
        self.assertTrue(status_resp.data["complete"])

    def test_workflow_multiple_files_per_eye(self) -> None:
        """Camera uploads multiple images for the same eye."""
        self.create_camera_session(self.rs)
        self._resolve()

        f1 = SimpleUploadedFile(
            "105-60-00224-7_Retina_OD_001.jpg",
            b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            "image/jpeg",
        )
        resp1 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f1, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(resp1.status_code, 201)

        f2 = SimpleUploadedFile(
            "105-60-00224-7_Retina_OD_002.jpg",
            b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            "image/jpeg",
        )
        resp2 = self.client.post(
            "/api/retinopathy/105-10-0001-2/left/",
            {"file": f2, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(resp2.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 2)

    def test_workflow_complete_then_new_session_needed(self) -> None:
        """After completing, resolve returns no_eligible_session."""
        session = self.create_camera_session(self.rs)
        self._resolve()

        for ft in session.expected_file_types:
            self._upload("105-10-0001-2", ft)

        self.assertTrue(session.is_complete)

        # Next resolve sees all sessions complete
        response = self.client.post(
            "/api/retinopathy/resolve/",
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_eligible_session")

    def test_workflow_with_capture_datetime(self) -> None:
        """Full workflow with distinct capture_datetime on each image."""
        self.create_camera_session(self.rs)
        self._resolve()

        for file_type, dt in [
            ("left", "2026-05-21T10:30:00Z"),
            ("right", "2026-05-21T10:31:00Z"),
        ]:
            f = SimpleUploadedFile(
                f"{file_type}.jpg",
                b"\xff\xd8\xff\xe0" + b"\x00" * 100,
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
