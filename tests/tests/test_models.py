"""Tests for edc_retinopathy models."""

from __future__ import annotations

from clinicedc_constants import YES
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from edc_retinopathy.constants import REPORT_TYPE_COMBINED, REPORT_TYPE_PER_EYE
from edc_retinopathy.models import EyeExamRegister, SessionFile

from .mixins import RetinopathyTestCaseMixin

NOW = timezone.now


class EyeExamRegisterModelTests(RetinopathyTestCaseMixin):
    """Tests for the EyeExamRegister model."""

    def test_create_session(self) -> None:
        rs = self.create_registered_subject()
        session = self.create_eye_exam_register(rs)
        self.assertEqual(session.subject_identifier, "105-10-0001-2")
        self.assertIsNotNone(session.pk)

    def test_str(self) -> None:
        rs = self.create_registered_subject()
        session = self.create_eye_exam_register(rs)
        self.assertIn("105-10-0001-2", str(session))

    def test_multiple_sessions_same_subject(self) -> None:
        """Multiple sessions per subject are allowed (repeat visits)."""
        rs = self.create_registered_subject()
        for _ in range(3):
            self.create_eye_exam_register(rs)
        self.assertEqual(
            EyeExamRegister.objects.filter(
                subject_identifier="105-10-0001-2",
            ).count(),
            3,
        )

    def test_expected_file_types_combined(self) -> None:
        rs = self.create_registered_subject()
        session = self.create_eye_exam_register(rs, report_type=REPORT_TYPE_COMBINED)
        self.assertEqual(
            session.expected_file_types,
            frozenset({"left", "right", "report"}),
        )

    def test_expected_file_types_per_eye(self) -> None:
        rs = self.create_registered_subject()
        session = self.create_eye_exam_register(rs, report_type=REPORT_TYPE_PER_EYE)
        self.assertEqual(
            session.expected_file_types,
            frozenset({"left", "right", "left_report", "right_report"}),
        )

    def test_is_complete_combined(self) -> None:
        rs = self.create_registered_subject()
        eye_exam_register = self.create_eye_exam_register(rs, report_type=REPORT_TYPE_COMBINED)
        self.assertFalse(eye_exam_register.is_complete)
        for ft in ("left", "right", "report"):
            SessionFile.objects.create(
                eye_exam_register=eye_exam_register,
                file_type=ft,
                original_filename=f"{ft}.jpg",
                stored_filename=f"{ft}_stored.jpg",
                capture_datetime=NOW(),
            )
        self.assertTrue(eye_exam_register.is_complete)

    def test_is_complete_per_eye(self) -> None:
        rs = self.create_registered_subject()
        eye_exam_register = self.create_eye_exam_register(rs, report_type=REPORT_TYPE_PER_EYE)
        self.assertFalse(eye_exam_register.is_complete)
        for ft in ("left", "right", "left_report", "right_report"):
            SessionFile.objects.create(
                eye_exam_register=eye_exam_register,
                file_type=ft,
                original_filename=f"{ft}.ext",
                stored_filename=f"{ft}_stored.ext",
                capture_datetime=NOW(),
            )
        self.assertTrue(eye_exam_register.is_complete)

    def test_contraindicated_none_when_unanswered(self) -> None:
        rs = self.create_registered_subject()
        eye_exam_register = self.create_eye_exam_register(
            rs,
            visual_impairment="",
            retinal_conditions="",
            ocular_interventions="",
            photosensitive="",
            pregnant="",
        )
        self.assertIsNone(eye_exam_register.contraindicated)

    def test_contraindicated_true(self) -> None:

        rs = self.create_registered_subject()
        eye_exam_register = self.create_eye_exam_register(rs, visual_impairment=YES)
        self.assertTrue(eye_exam_register.contraindicated)

    def test_contraindicated_false(self) -> None:
        rs = self.create_registered_subject()
        eye_exam_register = self.create_eye_exam_register(rs)
        self.assertFalse(eye_exam_register.contraindicated)


class SessionFileModelTests(RetinopathyTestCaseMixin):
    """Tests for the SessionFile model."""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.eye_exam_register = self.create_eye_exam_register(self.rs)

    def test_create_file(self) -> None:
        sf = SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="left_eye.jpg",
            stored_filename="abc123.jpg",
            capture_datetime=NOW(),
        )
        self.assertEqual(sf.file_type, "left")
        self.assertIsNotNone(sf.pk)

    def test_str(self) -> None:
        sf = SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="left_eye.jpg",
            stored_filename="abc123.jpg",
            capture_datetime=NOW(),
        )
        self.assertIn("left_eye.jpg", str(sf))

    def test_unique_constraint_session_original_filename(self) -> None:
        """Cannot create two files with same session + original_filename."""
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="same.jpg",
            stored_filename="aaa.jpg",
            capture_datetime=NOW(),
        )
        with self.assertRaises(IntegrityError):
            SessionFile.objects.create(
                eye_exam_register=self.eye_exam_register,
                file_type="right",
                original_filename="same.jpg",
                stored_filename="bbb.jpg",
                capture_datetime=NOW(),
            )

    def test_different_file_types_allowed(self) -> None:
        """Different file_types on same session are allowed."""
        for ft, fn in [("left", "a.jpg"), ("right", "b.jpg"), ("report", "c.pdf")]:
            SessionFile.objects.create(
                eye_exam_register=self.eye_exam_register,
                file_type=ft,
                original_filename=fn,
                stored_filename=f"{ft}_stored",
                capture_datetime=NOW(),
            )
        self.assertEqual(SessionFile.objects.count(), 3)

    def test_same_file_type_different_sessions(self) -> None:
        """Same file_type on different sessions is allowed."""
        eye_exam_register2 = self.create_eye_exam_register(self.rs)
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
            capture_datetime=NOW(),
        )
        SessionFile.objects.create(
            eye_exam_register=eye_exam_register2,
            file_type="left",
            original_filename="b.jpg",
            stored_filename="bbb.jpg",
            capture_datetime=NOW(),
        )
        self.assertEqual(SessionFile.objects.count(), 2)

    def test_protect_on_delete(self) -> None:
        """Deleting a session with files raises ProtectedError."""

        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
            capture_datetime=NOW(),
        )
        with self.assertRaises(ProtectedError):
            self.eye_exam_register.delete()

    def test_files_related_name(self) -> None:
        """Session.files reverse relation works."""
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
            capture_datetime=NOW(),
        )
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="right",
            original_filename="b.jpg",
            stored_filename="bbb.jpg",
            capture_datetime=NOW(),
        )
        self.assertEqual(self.eye_exam_register.files.count(), 2)

    def test_stored_filename_unique(self) -> None:
        """stored_filename must be unique across all files."""
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="same_name.jpg",
            capture_datetime=NOW(),
        )
        rs2 = self.create_registered_subject(subject_identifier="105-10-0002-3")
        eye_exam_register2 = self.create_eye_exam_register(rs2)
        with self.assertRaises(IntegrityError):
            SessionFile.objects.create(
                eye_exam_register=eye_exam_register2,
                file_type="left",
                original_filename="b.jpg",
                stored_filename="same_name.jpg",
                capture_datetime=NOW(),
            )

    def test_capture_datetime_required(self) -> None:
        """capture_datetime is a required field."""
        with self.assertRaises(IntegrityError):
            SessionFile.objects.create(
                eye_exam_register=self.eye_exam_register,
                file_type="left",
                original_filename="a.jpg",
                stored_filename="no_capture.jpg",
            )
