"""Tests for the file upload endpoints (left, right, report)."""

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


def _make_image_file(
    name: str = "test.jpg",
    content_type: str = "image/jpeg",
    size: int = 1024,
) -> SimpleUploadedFile:
    """Create a minimal fake image file."""
    return SimpleUploadedFile(
        name=name,
        content=b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4),
        content_type=content_type,
    )


def _make_pdf_file(
    name: str = "report.pdf",
    size: int = 2048,
) -> SimpleUploadedFile:
    """Create a minimal fake PDF file."""
    return SimpleUploadedFile(
        name=name,
        content=b"%PDF-1.4" + b"\x00" * (size - 8),
        content_type="application/pdf",
    )


class FileUploadBaseTestCase(TestCase):
    """Base setup for file upload tests."""

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
        self.session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
            age=35,
        )
        self.subject_id = "105-10-0001-2"

    def _upload_url(self, file_type: str) -> str:
        return f"/api/retinopathy/{self.subject_id}/{file_type}/"


class LeftEyeUploadTests(FileUploadBaseTestCase):
    """Tests for POST /api/retinopathy/<subject_identifier>/left/"""

    def test_upload_left_eye_success(self) -> None:
        """Valid left eye image upload returns 201."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "left")
        self.assertEqual(response.data["session_id"], self.session.pk)
        self.assertEqual(RetinalImage.objects.count(), 1)

    def test_upload_left_eye_creates_retinal_image(self) -> None:
        """Upload creates a RetinalImage with correct metadata."""
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(name="left_eye_scan.jpg")},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertEqual(img.session, self.session)
        self.assertEqual(img.file_type, "left")
        self.assertEqual(img.original_filename, "left_eye_scan.jpg")
        self.assertTrue(img.stored_filename.endswith(".jpg"))
        self.assertEqual(img.content_type, "image/jpeg")
        self.assertGreater(img.file_size, 0)

    def test_upload_left_eye_file_saved_to_disk(self) -> None:
        """File is physically written to the storage directory."""
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertGreater(stored_path.stat().st_size, 0)

    def test_upload_left_eye_duplicate_rejected(self) -> None:
        """Second left eye upload for same session returns 409."""
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(name="another.jpg")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(RetinalImage.objects.count(), 1)


class RightEyeUploadTests(FileUploadBaseTestCase):
    """Tests for POST /api/retinopathy/<subject_identifier>/right/"""

    def test_upload_right_eye_success(self) -> None:
        """Valid right eye image upload returns 201."""
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "right")

    def test_upload_right_eye_duplicate_rejected(self) -> None:
        """Second right eye upload for same session returns 409."""
        self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file()},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 409)


class ReportUploadTests(FileUploadBaseTestCase):
    """Tests for POST /api/retinopathy/<subject_identifier>/report/"""

    def test_upload_report_success(self) -> None:
        """Valid report PDF upload returns 201."""
        response = self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "report")

    def test_upload_report_file_saved_to_disk(self) -> None:
        """Report PDF is physically written to storage."""
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file()},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertTrue(img.stored_filename.endswith(".pdf"))
        self.assertEqual(img.content_type, "application/pdf")

    def test_upload_report_duplicate_rejected(self) -> None:
        """Second report upload for same session returns 409."""
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file()},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 409)


class FileUploadEdgeCaseTests(FileUploadBaseTestCase):
    """Edge cases and error handling for file uploads."""

    def test_invalid_file_type_rejected(self) -> None:
        """Unknown file_type in URL returns 400."""
        response = self.client.post(
            self._upload_url("middle"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file type", response.data["error"])

    def test_no_session_returns_404(self) -> None:
        """Upload for subject with no session returns 404."""
        RegisteredSubject.objects.create(
            subject_identifier="105-10-0099-9",
            initials="ZZ",
            gender="F",
        )
        response = self.client.post(
            "/api/retinopathy/105-10-0099-9/left/",
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_file_returns_400(self) -> None:
        """Request without a file field returns 400."""
        response = self.client.post(
            self._upload_url("left"),
            {},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self) -> None:
        """Request without token returns 401."""
        client = APIClient()
        response = client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 401)

    def test_all_three_file_types_on_one_session(self) -> None:
        """A complete workflow: left + right + report on one session."""
        for file_type, make_file in [
            ("left", _make_image_file),
            ("right", _make_image_file),
            ("report", _make_pdf_file),
        ]:
            response = self.client.post(
                self._upload_url(file_type),
                {"file": make_file()},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, f"Failed for {file_type}")

        self.assertEqual(RetinalImage.objects.count(), 3)
        self.assertEqual(self.session.files.count(), 3)

        file_types = set(
            RetinalImage.objects.values_list("file_type", flat=True)
        )
        self.assertEqual(file_types, {"left", "right", "report"})

    def test_upload_uses_most_recent_session(self) -> None:
        """When multiple sessions exist, upload links to the most recent."""
        older_session = self.session  # created in setUp
        newer_session = RetinopathySession.objects.create(
            subject_identifier=self.subject_id,
            initials="JD",
            sex="M",
            age=35,
        )
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertEqual(img.session, newer_session)
        self.assertNotEqual(img.session, older_session)

    def test_stored_filename_is_uuid_based(self) -> None:
        """Stored filename uses UUID, not the original name."""
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(name="patient_scan_secret.jpg")},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertNotIn("patient", img.stored_filename)
        self.assertNotIn("secret", img.stored_filename)
        self.assertEqual(len(img.stored_filename), 36)  # 32 hex + '.jpg'

    def test_file_extension_preserved(self) -> None:
        """Original file extension is preserved on stored filename."""
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(name="scan.png", content_type="image/png")},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertTrue(img.stored_filename.endswith(".png"))

    def test_default_extension_for_report(self) -> None:
        """Report without extension gets .pdf default."""
        pdf = SimpleUploadedFile(
            name="report",
            content=b"%PDF-1.4" + b"\x00" * 100,
            content_type="application/pdf",
        )
        self.client.post(
            self._upload_url("report"),
            {"file": pdf},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertTrue(img.stored_filename.endswith(".pdf"))

    def test_default_extension_for_image(self) -> None:
        """Image without extension gets .jpg default."""
        img_file = SimpleUploadedFile(
            name="image",
            content=b"\xff\xd8\xff\xe0" + b"\x00" * 100,
            content_type="image/jpeg",
        )
        self.client.post(
            self._upload_url("left"),
            {"file": img_file},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertTrue(img.stored_filename.endswith(".jpg"))
