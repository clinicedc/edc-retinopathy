"""Tests for the file upload endpoints (left, right, report)."""

from __future__ import annotations

import hashlib
import uuid as _uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from edc_retinopathy.models import CameraSession, SessionFile

from .mixins import RetinopathyTestCaseMixin

CAPTURE_DT = "2026-05-21T10:30:00Z"


def _make_image_file(
    name: str = "test.jpg",
    content_type: str = "image/jpeg",
    size: int = 1024,
) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"\xff\xd8\xff\xe0" + b"\x00" * (size - 4),
        content_type=content_type,
    )


def _make_png_file(name: str = "test.png", size: int = 1024) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8),
        content_type="image/png",
    )


def _make_pdf_file(name: str = "report.pdf", size: int = 2048) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"%PDF-1.4" + b"\x00" * (size - 8),
        content_type="application/pdf",
    )


def _make_invalid_file(name: str = "garbage.jpg", size: int = 512) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name=name,
        content=b"THIS IS NOT AN IMAGE" + b"\x00" * (size - 20),
        content_type="image/jpeg",
    )


class FileUploadBaseTestCase(RetinopathyTestCaseMixin):
    """Base setup for file upload tests."""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.session = self.create_camera_session(self.rs)
        self.subject_id = "105-10-0001-2"

    def _upload_url(self, file_type: str) -> str:
        return f"/api/retinopathy/{self.subject_id}/{file_type}/"


class LeftEyeUploadTests(FileUploadBaseTestCase):

    def test_upload_left_eye_success(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "left")
        self.assertEqual(str(response.data["session_id"]), str(self.session.pk))
        self.assertEqual(SessionFile.objects.count(), 1)

    def test_upload_left_eye_creates_session_file(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="left_eye_scan.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertEqual(img.session, self.session)
        self.assertEqual(img.file_type, "left")
        self.assertEqual(img.original_filename, "left_eye_scan.jpg")
        self.assertTrue(img.stored_filename.endswith(".jpg"))
        self.assertEqual(img.file_content_type, "image/jpeg")
        self.assertGreater(img.file_size, 0)

    def test_upload_left_eye_file_saved_to_disk(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertGreater(stored_path.stat().st_size, 0)

    def test_upload_left_eye_replacement(self) -> None:
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
        self.assertEqual(SessionFile.objects.count(), 1)
        self.assertEqual(response.data["file_type"], "left")
        self.assertNotEqual(response.data["id"], resp1.data["id"])


class RightEyeUploadTests(FileUploadBaseTestCase):

    def test_upload_right_eye_success(self) -> None:
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "right")

    def test_upload_right_eye_replacement(self) -> None:
        self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": "2026-05-21T11:00:00Z"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 1)


class ReportUploadTests(FileUploadBaseTestCase):

    def test_upload_report_success(self) -> None:
        response = self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "report")

    def test_upload_report_file_saved_to_disk(self) -> None:
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / img.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertTrue(img.stored_filename.endswith(".pdf"))
        self.assertEqual(img.file_content_type, "application/pdf")

    def test_upload_report_replacement(self) -> None:
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": "2026-05-21T11:00:00Z"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 1)


class ContentValidationTests(FileUploadBaseTestCase):

    def test_invalid_content_for_image_rejected(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_invalid_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_content")

    def test_invalid_content_for_report_rejected(self) -> None:
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
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_png_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_empty_file_rejected(self) -> None:
        empty = SimpleUploadedFile(name="empty.jpg", content=b"", content_type="image/jpeg")
        response = self.client.post(
            self._upload_url("left"),
            {"file": empty, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class FileSizeLimitTests(FileUploadBaseTestCase):

    @override_settings(EDC_RETINOPATHY_MAX_FILE_SIZE_MB=0.001)
    def test_oversized_file_rejected(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(size=2048), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "file_too_large")

    @override_settings(EDC_RETINOPATHY_MAX_FILE_SIZE_MB=10)
    def test_file_within_limit_accepted(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(size=1024), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class SessionExpiryTests(FileUploadBaseTestCase):

    @override_settings(EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES=30)
    def test_expired_session_not_found(self) -> None:
        old_time = timezone.now() - timedelta(minutes=60)
        CameraSession.objects.filter(pk=self.session.pk).update(
            report_datetime=old_time
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_fresh_session_accepted(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    @override_settings(EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES=120)
    def test_custom_expiry_setting(self) -> None:
        old_time = timezone.now() - timedelta(minutes=90)
        CameraSession.objects.filter(pk=self.session.pk).update(
            report_datetime=old_time
        )
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class CaptureDateTimeTests(FileUploadBaseTestCase):

    def test_capture_datetime_stored(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": "2026-05-21T10:30:00Z"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        img = SessionFile.objects.get()
        self.assertIsNotNone(img.capture_datetime)

    def test_capture_datetime_required(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)


class FileUploadEdgeCaseTests(FileUploadBaseTestCase):

    def test_invalid_file_type_rejected(self) -> None:
        response = self.client.post(
            self._upload_url("middle"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_file_type")

    def test_no_session_returns_404(self) -> None:
        self.create_registered_subject(
            subject_identifier="105-10-0099-9", initials="ZZ", gender="F"
        )
        response = self.client.post(
            "/api/retinopathy/105-10-0099-9/left/",
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_missing_file_returns_400(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_returns_401(self) -> None:
        client = APIClient()
        response = client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 401)

    def test_all_three_file_types_on_one_session(self) -> None:
        for file_type, make_file in [
            ("left", lambda: _make_image_file(name="left.jpg")),
            ("right", lambda: _make_image_file(name="right.jpg")),
            ("report", _make_pdf_file),
        ]:
            response = self.client.post(
                self._upload_url(file_type),
                {"file": make_file(), "capture_datetime": CAPTURE_DT},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201, f"Failed for {file_type}")
        self.assertEqual(SessionFile.objects.count(), 3)
        self.assertEqual(self.session.files.count(), 3)

    def test_upload_uses_most_recent_session(self) -> None:
        newer_session = self.create_camera_session(self.rs)
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertEqual(img.session, newer_session)
        self.assertNotEqual(img.session, self.session)

    def test_stored_filename_is_uuid_based(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="patient_scan_secret.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertNotIn("patient", img.stored_filename)
        self.assertNotIn("secret", img.stored_filename)
        self.assertEqual(len(img.stored_filename), 36)  # 32 hex + '.jpg'

    def test_file_extension_preserved(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {"file": _make_png_file(name="scan.png"), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertTrue(img.stored_filename.endswith(".png"))

    def test_default_extension_for_report(self) -> None:
        pdf = SimpleUploadedFile(
            name="report", content=b"%PDF-1.4" + b"\x00" * 100, content_type="application/pdf"
        )
        self.client.post(
            self._upload_url("report"),
            {"file": pdf, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertTrue(img.stored_filename.endswith(".pdf"))

    def test_default_extension_for_image(self) -> None:
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
        img = SessionFile.objects.get()
        self.assertTrue(img.stored_filename.endswith(".jpg"))


class ChecksumTests(FileUploadBaseTestCase):

    def _sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def test_correct_checksum_accepted(self) -> None:
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

    def test_wrong_checksum_rejected(self) -> None:
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
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
        self.assertEqual(SessionFile.objects.count(), 0)
        new_files = set(storage.iterdir()) - files_before
        self.assertEqual(len(new_files), 0)

    def test_checksum_is_optional(self) -> None:
        response = self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_checksum_case_insensitive(self) -> None:
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

    def test_upload_to_specific_session(self) -> None:
        older = self.session
        self.create_camera_session(self.rs)
        url = f"{self._upload_url('left')}?session_id={older.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        img = SessionFile.objects.get()
        self.assertEqual(img.session, older)

    def test_invalid_session_id_returns_404(self) -> None:
        url = f"{self._upload_url('left')}?session_id={_uuid.uuid4()}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_id_wrong_subject_returns_404(self) -> None:
        rs2 = self.create_registered_subject(
            subject_identifier="105-10-0099-9", initials="ZZ", gender="F"
        )
        other_session = self.create_camera_session(rs2)
        url = f"{self._upload_url('left')}?session_id={other_session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_session_id_bypasses_expiry(self) -> None:
        old_time = timezone.now() - timedelta(hours=12)
        CameraSession.objects.filter(pk=self.session.pk).update(
            report_datetime=old_time
        )
        url = f"{self._upload_url('left')}?session_id={self.session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
