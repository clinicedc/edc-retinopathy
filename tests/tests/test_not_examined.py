"""Tests for the "subjects not yet examined" report."""

from __future__ import annotations

from datetime import date
from typing import Any

from clinicedc_constants import NO
from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone
from edc_utils import age, get_utcnow

from edc_retinopathy.models import ContactAttempt, RegisteredSubjectProxy
from edc_retinopathy.views import NotExaminedView
from edc_retinopathy.views.not_examined_view import _decorate

from .mixins import RetinopathyTestCaseMixin


class NotExaminedTests(RetinopathyTestCaseMixin):
    """Tests for NotExaminedView."""

    @staticmethod
    def _queryset() -> QuerySet[dict[str, Any]]:
        return NotExaminedView().get_queryset()

    def _create_contact_attempt(
        self,
        registered_subject,
        number_of_attempts: int = 3,
    ) -> ContactAttempt:
        return ContactAttempt.objects.create(
            registered_subject_id=registered_subject.id,
            report_datetime=timezone.now(),
            number_of_attempts=number_of_attempts,
            contact_made=NO,
            site_id=settings.SITE_ID,
        )

    def test_subject_without_camera_session_is_listed(self) -> None:
        self.create_registered_subject("105-10-0001-2")

        self.assertEqual(
            [row["subject_identifier"] for row in self._queryset()],
            ["105-10-0001-2"],
        )

    def test_subject_with_camera_session_is_excluded(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        self.create_camera_session(registered_subject)

        self.assertEqual(self._queryset().count(), 0)

    def test_only_subjects_without_a_session_are_listed(self) -> None:
        examined = self.create_registered_subject("105-10-0001-2", initials="AA")
        self.create_camera_session(examined)
        self.create_registered_subject("105-10-0002-3", initials="BB")
        self.create_registered_subject("105-10-0003-4", initials="CC")

        # Ordered by subject_identifier ascending.
        self.assertEqual(
            [row["subject_identifier"] for row in self._queryset()],
            ["105-10-0002-3", "105-10-0003-4"],
        )

    def test_a_second_session_does_not_re_list_the_subject(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        self.create_camera_session(registered_subject)
        self.create_camera_session(registered_subject)

        self.assertEqual(self._queryset().count(), 0)

    def test_contact_attempt_is_annotated(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        contact_attempt = self._create_contact_attempt(
            registered_subject,
            number_of_attempts=3,
        )

        row = self._queryset().get()

        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["contact_attempt_pk"], contact_attempt.id)
        self.assertEqual(row["last_attempt"], contact_attempt.report_datetime)

    def test_without_contact_attempt_annotations_are_none(self) -> None:
        self.create_registered_subject("105-10-0001-2")

        row = self._queryset().get()

        self.assertIsNone(row["attempts"])
        self.assertIsNone(row["contact_attempt_pk"])
        self.assertIsNone(row["last_attempt"])

    def test_encrypted_fields_are_not_selected(self) -> None:
        """Selecting encrypted fields decrypts them per row, which is slow.

        They are neither displayed nor needed, so they must stay out of the
        query. This guards the report against a silent switch back to model
        instances.
        """
        self.create_registered_subject("105-10-0001-2")

        sql = str(self._queryset().query)

        for encrypted_field in (
            "first_name",
            "last_name",
            "full_name",
            "familiar_name",
            "initials",
            "identity",
        ):
            self.assertNotIn(encrypted_field, sql)

    def test_decorate_sets_age(self) -> None:
        dob = date(1990, 6, 15)
        self.create_registered_subject("105-10-0001-2", dob=dob)

        row = _decorate(list(self._queryset()))[0]

        self.assertEqual(row["age_in_years"], age(dob, get_utcnow()).years)

    def test_decorate_tolerates_a_null_dob(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        RegisteredSubjectProxy.objects.filter(pk=registered_subject.pk).update(dob=None)

        row = _decorate(list(self._queryset()))[0]

        self.assertIsNone(row["age_in_years"])
