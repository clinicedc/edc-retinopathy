"""Tests for edc_retinopathy models."""

from __future__ import annotations

from django.db import IntegrityError
from django.test import TestCase

from ..models import RetinalImage, RetinopathySession


class RetinopathySessionModelTests(TestCase):
    """Tests for the RetinopathySession model."""

    def test_create_session(self) -> None:
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            sex="M",
            age=35,
        )
        self.assertEqual(session.subject_identifier, "105-10-0001-2")
        self.assertIsNotNone(session.created_datetime)

    def test_str(self) -> None:
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )
        self.assertIn("105-10-0001-2", str(session))

    def test_multiple_sessions_same_subject(self) -> None:
        """Multiple sessions per subject are allowed (repeat visits)."""
        for _ in range(3):
            RetinopathySession.objects.create(
                subject_identifier="105-10-0001-2",
            )
        self.assertEqual(
            RetinopathySession.objects.filter(
                subject_identifier="105-10-0001-2"
            ).count(),
            3,
        )

    def test_ordering_most_recent_first(self) -> None:
        s1 = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )
        s2 = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )
        sessions = list(RetinopathySession.objects.all())
        self.assertEqual(sessions[0], s2)
        self.assertEqual(sessions[1], s1)

    def test_optional_fields_default(self) -> None:
        session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )
        self.assertEqual(session.initials, "")
        self.assertEqual(session.sex, "")
        self.assertIsNone(session.age)
        self.assertEqual(session.device_id, "")
        self.assertEqual(session.site_id, "")


class RetinalImageModelTests(TestCase):
    """Tests for the RetinalImage model."""

    def setUp(self) -> None:
        self.session = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )

    def test_create_image(self) -> None:
        img = RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="left_eye.jpg",
            stored_filename="abc123.jpg",
        )
        self.assertEqual(img.file_type, "left")
        self.assertIsNotNone(img.pk)

    def test_str(self) -> None:
        img = RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="left_eye.jpg",
            stored_filename="abc123.jpg",
        )
        self.assertIn("left_eye.jpg", str(img))

    def test_unique_constraint_session_file_type(self) -> None:
        """Cannot create two images with same session + file_type."""
        RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="first.jpg",
            stored_filename="aaa.jpg",
        )
        with self.assertRaises(IntegrityError):
            RetinalImage.objects.create(
                session=self.session,
                file_type="left",
                original_filename="second.jpg",
                stored_filename="bbb.jpg",
            )

    def test_different_file_types_allowed(self) -> None:
        """Different file_types on same session are allowed."""
        for ft, fn in [("left", "a.jpg"), ("right", "b.jpg"), ("report", "c.pdf")]:
            RetinalImage.objects.create(
                session=self.session,
                file_type=ft,
                original_filename=fn,
                stored_filename=f"{ft}_stored",
            )
        self.assertEqual(RetinalImage.objects.count(), 3)

    def test_same_file_type_different_sessions(self) -> None:
        """Same file_type on different sessions is allowed."""
        session2 = RetinopathySession.objects.create(
            subject_identifier="105-10-0001-2",
        )
        RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
        )
        RetinalImage.objects.create(
            session=session2,
            file_type="left",
            original_filename="b.jpg",
            stored_filename="bbb.jpg",
        )
        self.assertEqual(RetinalImage.objects.count(), 2)

    def test_protect_on_delete(self) -> None:
        """Deleting a session with files raises ProtectedError."""
        from django.db.models import ProtectedError

        RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
        )
        with self.assertRaises(ProtectedError):
            self.session.delete()

    def test_files_related_name(self) -> None:
        """Session.files reverse relation works."""
        RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="aaa.jpg",
        )
        RetinalImage.objects.create(
            session=self.session,
            file_type="right",
            original_filename="b.jpg",
            stored_filename="bbb.jpg",
        )
        self.assertEqual(self.session.files.count(), 2)

    def test_stored_filename_unique(self) -> None:
        """stored_filename must be unique across all images."""
        RetinalImage.objects.create(
            session=self.session,
            file_type="left",
            original_filename="a.jpg",
            stored_filename="same_name.jpg",
        )
        session2 = RetinopathySession.objects.create(
            subject_identifier="105-10-0002-3",
        )
        with self.assertRaises(IntegrityError):
            RetinalImage.objects.create(
                session=session2,
                file_type="left",
                original_filename="b.jpg",
                stored_filename="same_name.jpg",
            )
