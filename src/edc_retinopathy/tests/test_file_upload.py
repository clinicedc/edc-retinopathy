"""Tests for the file upload endpoints (left, right, report)."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import RetinalImage, RetinopathySession
from .models import RegisteredSubject

CAPTURE_DT = "2026-05-21T10:30:00Z"


def _make_image_file(
    name: str = "test.jpg",
    content_type: str = "image/jpeg",
    size: int = 1024,
) -> SimpleUploadedFile:
    """Create a minimal fake JPEG file with valid magic bytes."""
    return SimpleUploadedFile(
        name=name,
        content=b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4),
        content_type=content_type,
    )


def _make_png_file(
    name: str = "test.png",
    size: int = 1024,
) -> SimpleUploadedFile:
    """Create a minimal fake PNG file with valid magic bytes."""
    return SimpleUploadedFile(
        name=name,
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8),
        content_type="image/png",
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


def _make_invalid_file(
    name: str = "garbage.jpg",
    size: int = 512,
) -> SimpleUploadedFile:
    """Create a file with invalid content (no valid magic bytes)."""
    return SimpleUploadedFile(
        name=name,
        content=b"THIS IS NOT AN IMAGE" + b"\x00" * (size - 20),
        content_type="image/jpeg",
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
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
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
            {
                "file": _make_image_file(name="left_eye_scan.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
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
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertGreater(stored_path.stat().st_size, 0)

    def test_upload_left_eye_replacement(self) -> None:
        """Second left eye upload replaces the first (201, new record)."""
        resp1 = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(resp1.status_code, 201)
        response = self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="another.jpg"),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RetinalImage.objects.count(), 1)
        self.assertEqual(response.data["file_type"], "left")
        self.assertNotEqual(response.data["id"], resp1.data["id"])


class RightEyeUploadTests(FileUploadBaseTestCase):
    """Tests for POST /api/retinopathy/<subject_identifier>/right/"""

    def test_upload_right_eye_success(self) -> None:
        """Valid right eye image upload returns 201."""
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "right")

    def test_upload_right_eye_replacement(self) -> None:
        """Second right eye upload replaces the first (201)."""
        self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("right"),
            {
                "file": _make_image_file(),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RetinalImage.objects.count(), 1)


class ReportUploadTests(FileUploadBaseTestCase):
    """Tests for POST /api/retinopathy/<subject_identifier>/report/"""

    def test_upload_report_success(self) -> None:
        """Valid report PDF upload returns 201."""
        response = self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "report")

    def test_upload_report_file_saved_to_disk(self) -> None:
        """Report PDF is physically written to storage."""
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertTrue(img.stored_filename.endswith(".pdf"))
        self.assertEqual(img.content_type, "application/pdf")

    def test_upload_report_replacement(self) -> None:
        """Second report upload replaces the first (201)."""
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("report"),
            {
                "file": _make_pdf_file(),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RetinalImage.objects.count(), 1)


class ContentValidationTests(FileUploadBaseTestCase):
    """Tests for magic-byte content validation."""

    def test_invalid_content_for_image_rejected(self) -> None:
        """Non-JPEG/PNG file sent as image returns 400."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_invalid_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_content")

    def test_invalid_content_for_report_rejected(self) -> None:
        """Non-PDF file sent as report returns 400."""
        bad_pdf = SimpleUploadedFile(
            name="report.pdf",
            content=b"NOT A PDF FILE" + b"\x00" * 100,
            content_type="application/pdf",
        )
        response = self.client.post(
            self._upload_url("report"),
            {"file": bad_pdf, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_content")

    def test_png_accepted_for_image(self) -> None:
        """PNG files are accepted for eye images."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_png_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_empty_file_rejected(self) -> None:
        """Empty file returns 400."""
        empty = SimpleUploadedFile(
            name="empty.jpg", content=b"", content_type="image/jpeg"
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": empty, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class FileSizeLimitTests(FileUploadBaseTestCase):
    """Tests for file size limits."""

    @override_settings(EDC_RETINOPATHY_MAX_FILE_SIZE_MB=0.001)
    def test_oversized_file_rejected(self) -> None:
        """File exceeding max size returns 400."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(size=2048), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "file_too_large")

    @override_settings(EDC_RETINOPATHY_MAX_FILE_SIZE_MB=10)
    def test_file_within_limit_accepted(self) -> None:
        """File within max size is accepted."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(size=1024), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class SessionExpiryTests(FileUploadBaseTestCase):
    """Tests for session staleness guard."""

    @override_settings(EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES=30)
    def test_expired_session_not_found(self) -> None:
        """Upload to a session older than expire minutes returns 404."""
        old_time = timezone.now() - timedelta(minutes=60)
        RetinopathySession.objects.filter(pk=self.session.pk).update(
            created_datetime=old_time
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_fresh_session_accepted(self) -> None:
        """Upload to a recent session succeeds."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    @override_settings(EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES=120)
    def test_custom_expiry_setting(self) -> None:
        """Custom expiry window is respected."""
        old_time = timezone.now() - timedelta(minutes=90)
        RetinopathySession.objects.filter(pk=self.session.pk).update(
            created_datetime=old_time
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class CaptureDateTimeTests(FileUploadBaseTestCase):
    """Tests for capture_datetime metadata."""

    def test_capture_datetime_stored(self) -> None:
        """capture_datetime from the payload is saved on the record."""
        dt = "2026-05-21T10:30:00Z"
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": dt},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        img = RetinalImage.objects.get()
        self.assertIsNotNone(img.capture_datetime)

    def test_capture_datetime_required(self) -> None:
        """Upload without capture_datetime returns 400."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class FileUploadEdgeCaseTests(FileUploadBaseTestCase):
    """Edge cases and error handling for file uploads."""

    def test_invalid_file_type_rejected(self) -> None:
        """Unknown file_type in URL returns 400."""
        response = self.client.post(
            self._upload_url("middle"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_file_type")

    def test_no_session_returns_404(self) -> None:
        """Upload for subject with no session returns 404."""
        RegisteredSubject.objects.create(
            subject_identifier="105-10-0099-9",
            initials="ZZ",
            gender="F",
        )
        response = self.client.post(
            "/api/retinopathy/105-10-0099-9/left/",
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_file_returns_400(self) -> None:
        """Request without a file field returns 400."""
        response = self.client.post(
            self._upload_url("left"),
            {"capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self) -> None:
        """Request without token returns 401."""
        client = APIClient()
        response = client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
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
                {"file": make_file(), "capture_datetime": CAPTURE_DT},
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
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertEqual(img.session, newer_session)
        self.assertNotEqual(img.session, older_session)

    def test_stored_filename_is_uuid_based(self) -> None:
        """Stored filename uses UUID, not the original name."""
        self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="patient_scan_secret.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
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
            {"file": _make_png_file(name="scan.png"), "capture_datetime": CAPTURE_DT},
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
            {"file": pdf, "capture_datetime": CAPTURE_DT},
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
            {"file": img_file, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = RetinalImage.objects.get()
        self.assertTrue(img.stored_filename.endswith(".jpg"))


class ChecksumTests(FileUploadBaseTestCase):
    """Tests for SHA-256 checksum verification."""

    def _sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def test_correct_checksum_accepted(self) -> None:
        """Upload with matching checksum succeeds."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        response = self.client.post(
            self._upload_url("left"),
            {
                "file": SimpleUploadedFile("left.jpg", content, "image/jpeg"),
                "capture_datetime": CAPTURE_DT,
                "checksum": self._sha256(content),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RetinalImage.objects.count(), 1)

    def test_wrong_checksum_rejected(self) -> None:
        """Upload with mismatched checksum returns 400 and no DB record."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        # Count files before upload
        storage = Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images"
        files_before = set(storage.iterdir())

        response = self.client.post(
            self._upload_url("left"),
            {
                "file": SimpleUploadedFile("left.jpg", content, "image/jpeg"),
                "capture_datetime": CAPTURE_DT,
                "checksum": "0" * 64,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "checksum_mismatch")
        self.assertEqual(RetinalImage.objects.count(), 0)

        # Verify the corrupt file was cleaned up (no new files on disk)
        files_after = set(storage.iterdir())
        new_files = files_after - files_before
        self.assertEqual(len(new_files), 0)

    def test_checksum_is_optional(self) -> None:
        """Upload without checksum still succeeds (no verification)."""
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_checksum_case_insensitive(self) -> None:
        """Checksum comparison is case-insensitive."""
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        response = self.client.post(
            self._upload_url("left"),
            {
                "file": SimpleUploadedFile("left.jpg", content, "image/jpeg"),
                "capture_datetime": CAPTURE_DT,
                "checksum": self._sha256(content).upper(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class SessionIdParamTests(FileUploadBaseTestCase):
    """Tests for explicit session_id query parameter."""

    def test_upload_to_specific_session(self) -> None:
        """Upload with ?session_id targets that session."""
        older = self.session
        RetinopathySession.objects.create(
            subject_identifier=self.subject_id,
            initials="JD",
            sex="M",
        )
        # Upload to the OLDER session explicitly
        url = f"{self._upload_url('left')}?session_id={older.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        img = RetinalImage.objects.get()
        self.assertEqual(img.session, older)

    def test_invalid_session_id_returns_404(self) -> None:
        """Non-existent session_id returns 404."""
        import uuid as _uuid

        url = f"{self._upload_url('left')}?session_id={_uuid.uuid4()}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_id_wrong_subject_returns_404(self) -> None:
        """session_id for a different subject returns 404."""
        other_session = RetinopathySession.objects.create(
            subject_identifier="105-10-0099-9",
            initials="ZZ",
            sex="F",
        )
        url = f"{self._upload_url('left')}?session_id={other_session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_id_bypasses_expiry(self) -> None:
        """Explicit session_id is not subject to expiry check."""
        old_time = timezone.now() - timedelta(hours=12)
        RetinopathySession.objects.filter(pk=self.session.pk).update(
            created_datetime=old_time
        )
        url = f"{self._upload_url('left')}?session_id={self.session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
