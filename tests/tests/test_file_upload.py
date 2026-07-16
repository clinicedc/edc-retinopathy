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


def _make_dicom_file(name: str = "scan.dcm", size: int = 2048) -> SimpleUploadedFile:
    """Create a minimal DICOM file (128-byte preamble + DICM magic)."""
    preamble = b"\x00" * 128
    magic = b"DICM"
    padding = b"\x00" * (size - 132)
    return SimpleUploadedFile(
        name=name,
        content=preamble + magic + padding,
        content_type="application/dicom",
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
        self.camera_session = self.create_camera_session(self.rs)
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
        self.assertEqual(str(response.data["camera_session_id"]), str(self.camera_session.pk))
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
        self.assertEqual(img.camera_session, self.camera_session)
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

    def test_upload_multiple_left_eye_files(self) -> None:
        """Multiple files with the same file_type are allowed."""
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
        self.assertEqual(SessionFile.objects.count(), 2)
        self.assertEqual(response.data["file_type"], "left")


class RightEyeUploadTests(FileUploadBaseTestCase):
    def test_upload_right_eye_success(self) -> None:
        response = self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "right")

    def test_upload_multiple_right_eye_files(self) -> None:
        self.client.post(
            self._upload_url("right"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("right"),
            {
                "file": _make_image_file(name="another.jpg"),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 2)


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

    def test_upload_multiple_reports(self) -> None:
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("report"),
            {
                "file": _make_pdf_file(name="report2.pdf"),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 2)


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
        self.assertEqual(self.camera_session.files.count(), 3)

    def test_upload_uses_most_recent_session(self) -> None:
        newer_camera_session = self.create_camera_session(self.rs)
        self.client.post(
            self._upload_url("left"),
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertEqual(img.camera_session, newer_camera_session)
        self.assertNotEqual(img.camera_session, self.camera_session)

    def test_stored_filename_uses_original_name(self) -> None:
        """Stored filename is <session_pk>/<original_filename>."""
        self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="fundus_OD_20260602.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertEqual(
            img.stored_filename,
            f"{self.camera_session.pk}/fundus_OD_20260602.jpg",
        )

    def test_file_extension_preserved(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {"file": _make_png_file(name="scan.png"), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        img = SessionFile.objects.get()
        self.assertTrue(img.stored_filename.endswith(".png"))

    def test_original_filename_preserved_for_report(self) -> None:
        self.client.post(
            self._upload_url("report"),
            {"file": _make_pdf_file(name="my_report.pdf"), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        sf = SessionFile.objects.get()
        self.assertEqual(sf.original_filename, "my_report.pdf")
        self.assertTrue(sf.stored_filename.endswith("/my_report.pdf"))

    def test_original_filename_preserved_for_image(self) -> None:
        self.client.post(
            self._upload_url("left"),
            {
                "file": _make_image_file(name="105-60-00224-7_Retina_OD.jpg"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        sf = SessionFile.objects.get()
        self.assertEqual(sf.original_filename, "105-60-00224-7_Retina_OD.jpg")


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
        # File should have been cleaned up from disk
        session_dir = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR)
            / "images"
            / str(self.camera_session.pk)
        )
        if session_dir.exists():
            self.assertEqual(
                [f for f in session_dir.iterdir() if not f.name.startswith(".")],
                [],
            )

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


class DuplicateUploadTests(FileUploadBaseTestCase):
    """A retried upload (same filename) must not crash with a 500."""

    def test_identical_retry_is_idempotent(self) -> None:
        content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        payload = {
            "file": SimpleUploadedFile("left.jpg", content, "image/jpeg"),
            "capture_datetime": CAPTURE_DT,
        }
        first = self.client.post(self._upload_url("left"), payload, format="multipart")
        self.assertEqual(first.status_code, 201)

        retry_payload = {
            "file": SimpleUploadedFile("left.jpg", content, "image/jpeg"),
            "capture_datetime": CAPTURE_DT,
        }
        second = self.client.post(self._upload_url("left"), retry_payload, format="multipart")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(SessionFile.objects.count(), 1)

    def test_same_filename_different_content_returns_409(self) -> None:
        first_payload = {
            "file": SimpleUploadedFile(
                "left.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100, "image/jpeg",
            ),
            "capture_datetime": CAPTURE_DT,
        }
        first = self.client.post(self._upload_url("left"), first_payload, format="multipart")
        self.assertEqual(first.status_code, 201)

        conflicting_payload = {
            "file": SimpleUploadedFile(
                "left.jpg", b"\xff\xd8\xff\xe0" + b"\x11" * 100, "image/jpeg",
            ),
            "capture_datetime": CAPTURE_DT,
        }
        second = self.client.post(
            self._upload_url("left"),
            conflicting_payload,
            format="multipart",
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "filename_conflict")
        self.assertEqual(SessionFile.objects.count(), 1)

    def test_retry_of_dicom_upload_is_idempotent(self) -> None:
        content = (b"\x00" * 128) + b"DICM" + (b"\x00" * 1916)
        first = self.client.post(
            self._upload_url("right_dicom"),
            {
                "file": SimpleUploadedFile("scan.dcm", content, "application/dicom"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        self.assertEqual(first.status_code, 201)

        second = self.client.post(
            self._upload_url("right_dicom"),
            {
                "file": SimpleUploadedFile("scan.dcm", content, "application/dicom"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(SessionFile.objects.count(), 1)


class SessionIdParamTests(FileUploadBaseTestCase):
    def test_upload_to_specific_session(self) -> None:
        older_camera_session = self.camera_session
        self.create_camera_session(self.rs)
        url = f"{self._upload_url('left')}?camera_session_id={older_camera_session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        img = SessionFile.objects.get()
        self.assertEqual(img.camera_session, older_camera_session)

    def test_invalid_camera_session_id_returns_404(self) -> None:
        url = f"{self._upload_url('left')}?camera_session_id={_uuid.uuid4()}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_camera_session_id_wrong_subject_returns_404(self) -> None:
        rs2 = self.create_registered_subject(
            subject_identifier="105-10-0099-9",
            initials="ZZ",
            gender="F",
        )
        other_camera_session = self.create_camera_session(rs2)
        url = f"{self._upload_url('left')}?camera_session_id={other_camera_session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 404)

    def test_camera_session_id_bypasses_expiry(self) -> None:
        old_time = timezone.now() - timedelta(hours=12)
        CameraSession.objects.filter(pk=self.camera_session.pk).update(
            report_datetime=old_time,
        )
        url = f"{self._upload_url('left')}?camera_session_id={self.camera_session.pk}"
        response = self.client.post(
            url,
            {"file": _make_image_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)


class DicomUploadTests(FileUploadBaseTestCase):
    def test_upload_left_dicom_success(self) -> None:
        response = self.client.post(
            self._upload_url("left_dicom"),
            {"file": _make_dicom_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "left_dicom")
        self.assertEqual(SessionFile.objects.count(), 1)

    def test_upload_right_dicom_success(self) -> None:
        response = self.client.post(
            self._upload_url("right_dicom"),
            {"file": _make_dicom_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["file_type"], "right_dicom")

    def test_dicom_file_saved_to_disk(self) -> None:
        self.client.post(
            self._upload_url("left_dicom"),
            {"file": _make_dicom_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        sf = SessionFile.objects.get()
        stored_path = (
            Path(settings.EDC_RETINOPATHY_STORAGE_DIR) / "images" / sf.stored_filename
        )
        self.assertTrue(stored_path.exists())
        self.assertTrue(sf.stored_filename.endswith(".dcm"))
        self.assertEqual(sf.file_content_type, "application/dicom")

    def test_dicom_multiple_files(self) -> None:
        self.client.post(
            self._upload_url("left_dicom"),
            {"file": _make_dicom_file(), "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        response = self.client.post(
            self._upload_url("left_dicom"),
            {
                "file": _make_dicom_file(name="rescan.dcm"),
                "capture_datetime": "2026-05-21T11:00:00Z",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SessionFile.objects.count(), 2)

    def test_invalid_dicom_rejected(self) -> None:
        bad_dcm = SimpleUploadedFile(
            name="bad.dcm",
            content=b"NOT A DICOM FILE" + b"\x00" * 200,
            content_type="application/dicom",
        )
        response = self.client.post(
            self._upload_url("left_dicom"),
            {"file": bad_dcm, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_content")

    def test_dicom_too_small_rejected(self) -> None:
        tiny_dcm = SimpleUploadedFile(
            name="tiny.dcm",
            content=b"\x00" * 100,
            content_type="application/dicom",
        )
        response = self.client.post(
            self._upload_url("left_dicom"),
            {"file": tiny_dcm, "capture_datetime": CAPTURE_DT},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "invalid_content")

    def test_dicom_original_filename_preserved(self) -> None:
        """DICOM original filename is kept."""
        self.client.post(
            self._upload_url("left_dicom"),
            {
                "file": _make_dicom_file(name="105-60-00224-7_Retina_OD.dcm"),
                "capture_datetime": CAPTURE_DT,
            },
            format="multipart",
        )
        sf = SessionFile.objects.get()
        self.assertEqual(sf.original_filename, "105-60-00224-7_Retina_OD.dcm")

    def test_dicom_does_not_affect_is_complete(self) -> None:
        """DICOM uploads are supplementary — session completes without them."""
        for ft in ("left", "right", "report"):
            if ft == "report":
                f = _make_pdf_file()
            else:
                f = _make_image_file(name=f"{ft}.jpg")
            self.client.post(
                self._upload_url(ft),
                {"file": f, "capture_datetime": CAPTURE_DT},
                format="multipart",
            )
        self.camera_session.refresh_from_db()
        self.assertTrue(self.camera_session.is_complete)
