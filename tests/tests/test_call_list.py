"""Tests for the "subjects not yet examined" report."""

from __future__ import annotations

from datetime import date
from typing import Any

from clinicedc_constants import NO, YES
from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone
from edc_utils import age, get_utcnow

from edc_retinopathy.models import CallList, RegisteredSubjectProxy
from edc_retinopathy.views import CallListView
from edc_retinopathy.views.call_list_view import (
    AGREED_CHOICES,
    AGREED_FILTER_CHOICES,
    NOT_CONTACTED,
    _decorate,
    _site_choices,
)

from .mixins import RetinopathyTestCaseMixin


class CallListTests(RetinopathyTestCaseMixin):
    """Tests for CallListView."""

    @staticmethod
    def _queryset() -> QuerySet[dict[str, Any]]:
        return CallListView().get_queryset()

    def _create_call_list(
        self,
        registered_subject,
        number_of_attempts: int = 3,
    ) -> CallList:
        return CallList.objects.create(
            registered_subject_id=registered_subject.id,
            report_datetime=timezone.now(),
            number_of_attempts=number_of_attempts,
            contact_made=NO,
            site_id=settings.SITE_ID,
        )

    def test_subject_without_eye_exam_register_is_listed(self) -> None:
        self.create_registered_subject("105-10-0001-2")

        self.assertEqual(
            [row["subject_identifier"] for row in self._queryset()],
            ["105-10-0001-2"],
        )

    def test_subject_with_eye_exam_register_is_excluded(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        self.create_eye_exam_register(registered_subject)

        self.assertEqual(self._queryset().count(), 0)

    def test_only_subjects_without_a_session_are_listed(self) -> None:
        examined = self.create_registered_subject("105-10-0001-2", initials="AA")
        self.create_eye_exam_register(examined)
        self.create_registered_subject("105-10-0002-3", initials="BB")
        self.create_registered_subject("105-10-0003-4", initials="CC")

        # Ordered by subject_identifier ascending.
        self.assertEqual(
            [row["subject_identifier"] for row in self._queryset()],
            ["105-10-0002-3", "105-10-0003-4"],
        )

    def test_a_second_session_does_not_re_list_the_subject(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        self.create_eye_exam_register(registered_subject)
        self.create_eye_exam_register(registered_subject)

        self.assertEqual(self._queryset().count(), 0)

    def test_call_list_is_annotated(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        call_list = self._create_call_list(
            registered_subject,
            number_of_attempts=3,
        )

        row = self._queryset().get()

        self.assertEqual(row["attempts"], 3)
        self.assertEqual(row["call_list_pk"], call_list.id)
        self.assertEqual(row["last_attempt"], call_list.report_datetime)

    def test_without_call_list_annotations_are_none(self) -> None:
        self.create_registered_subject("105-10-0001-2")

        row = self._queryset().get()

        self.assertIsNone(row["attempts"])
        self.assertIsNone(row["call_list_pk"])
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

    def test_site_choices_are_the_raw_site_ids(self) -> None:
        """The Site column renders site_id, so the filter must offer site ids.

        The DataTables column filter is an exact match against the rendered
        cell text, so the dropdown values have to be the same integers.
        """
        self.create_registered_subject("105-10-0001-2", initials="AA")
        self.create_registered_subject("105-10-0002-3", initials="BB")

        rows = list(self._queryset())

        self.assertEqual(_site_choices(rows), [settings.SITE_ID])

    def test_site_choices_are_sorted_and_distinct(self) -> None:
        rows = [{"site_id": 30}, {"site_id": 10}, {"site_id": 30}, {"site_id": 20}]

        self.assertEqual(_site_choices(rows), [10, 20, 30])

    def test_site_choices_omits_a_null_site(self) -> None:
        rows = [{"site_id": 10}, {"site_id": None}]

        self.assertEqual(_site_choices(rows), [10])

    def test_agreed_choices_are_valid_model_values(self) -> None:
        """The Agreed filter is an exact match on the raw stored value.

        If these drift from the field's choices the dropdown silently
        matches nothing, so pin them to the model.
        """
        field = CallList._meta.get_field("agreed_to_attend")
        valid = {value for value, _ in field.choices}

        self.assertTrue(set(AGREED_CHOICES).issubset(valid))

    def test_filter_choices_add_not_contacted_to_the_model_values(self) -> None:
        """`Not contacted` is a filter-only token, not a stored value.

        Rows with no contact attempt render an empty Agreed cell, and the
        filter reads "" as "no filter", so they need their own token.
        """
        field = CallList._meta.get_field("agreed_to_attend")
        valid = {value for value, _ in field.choices}

        self.assertEqual(AGREED_FILTER_CHOICES, (*AGREED_CHOICES, NOT_CONTACTED))
        self.assertNotIn(NOT_CONTACTED, valid)

    def test_agreed_is_annotated_from_the_call_list(self) -> None:
        registered_subject = self.create_registered_subject("105-10-0001-2")
        call_list = self._create_call_list(registered_subject)
        call_list.agreed_to_attend = YES
        call_list.save()

        row = self._queryset().get()

        self.assertEqual(row["agreed"], YES)
