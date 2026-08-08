"""View listing registered subjects who have not had a camera session."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from clinicedc_constants import NO, NOT_APPLICABLE, YES
from django.apps import apps as django_apps
from django.conf import settings
from django.db.models import DateTimeField, Exists, F, OuterRef, QuerySet, Subquery
from django.views.generic import ListView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin
from edc_utils import age, get_utcnow
from edc_visit_tracking.constants import MISSED_VISIT

from ..models import EyeExamRegister, RegisteredSubjectProxy

# Columns read from RegisteredSubject. It carries six encrypted fields
# (first_name, last_name, full_name, familiar_name, initials, identity) and
# each is decrypted per row when a model instance is materialized, so the
# report selects values() and no encrypted column may be listed here.
RS_FIELDS = (
    "id",
    "subject_identifier",
    "site_id",
    "gender",
    "dob",
)

# Options for the "Agreed" column filter. Taken from the constants rather than
# hardcoded in the template, since the DataTables filter is an exact match
# against the raw value rendered in the cell.
AGREED_CHOICES = (YES, NO, NOT_APPLICABLE)

# Subjects never contacted have no contact attempt, so the Agreed cell renders
# empty. The filter reads "" as "no filter", so those rows need a token of
# their own to be selectable. Rendered into data-search, never displayed.
NOT_CONTACTED = "Not contacted"

AGREED_FILTER_CHOICES = (*AGREED_CHOICES, NOT_CONTACTED)

# Added by get_queryset().
ANNOTATION_FIELDS = (
    "last_visit",
    "attempts",
    "agreed",
    "attend_date",
    "last_attempt",
    "contact_attempt_pk",
)

REPORT_VALUES = (*RS_FIELDS, *ANNOTATION_FIELDS)


def _decorate(
    rows: list[dict[str, Any]],
    reference_dt: datetime | None = None,
) -> list[dict[str, Any]]:
    """Add `age_in_years` to each row for the template."""
    reference_dt = reference_dt or get_utcnow()
    for row in rows:
        row["age_in_years"] = age(row["dob"], reference_dt).years if row["dob"] else None
    return rows


def _site_choices(rows: list[dict[str, Any]]) -> list[int]:
    """Return the sorted, distinct site ids present in the report.

    These are the raw integers rendered in the Site column, so the
    DataTables exact-match column filter compares like with like.
    """
    return sorted({row["site_id"] for row in rows if row["site_id"] is not None})


class CallListView(EdcViewMixin, NavbarViewMixin, ListView):
    """List registered subjects to be contacted to schedule an
    eye exam.
    """

    template_name = "edc_retinopathy/call_list.html"
    context_object_name = "registered_subjects"
    navbar_selected_item = "edc_lab_results"

    def get_queryset(self) -> QuerySet[dict[str, Any]]:
        has_eye_exam_register = Exists(
            EyeExamRegister.objects.filter(registered_subject=OuterRef("pk")),
        )
        last_visit = Subquery(
            self.subject_visit_model_cls.objects.filter(
                subject_identifier=OuterRef("subject_identifier"),
            )
            .exclude(reason=MISSED_VISIT)
            .order_by("-report_datetime")
            .values("report_datetime")[:1],
            output_field=DateTimeField(),
        )
        qs = (
            RegisteredSubjectProxy.objects.exclude(has_eye_exam_register)
            .annotate(
                last_visit=last_visit,
                attempts=F("contact_attempt__number_of_attempts"),
                last_attempt=F("contact_attempt__report_datetime"),
                contact_attempt_pk=F("contact_attempt__id"),
                attend_date=F("contact_attempt__agreed_to_attend_date"),
                agreed=F("contact_attempt__agreed_to_attend"),
            )
        )
        if self.filter_by_visit_datetime:
            qs = qs.filter(last_visit__gte=self.filter_by_visit_datetime)
        return qs.values(*REPORT_VALUES).order_by("subject_identifier")

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        rows = _decorate(list(context["registered_subjects"]))
        context["registered_subjects"] = rows
        context["object_list"] = rows
        context["site_choices"] = _site_choices(rows)
        context["agreed_choices"] = AGREED_FILTER_CHOICES
        context["not_contacted"] = NOT_CONTACTED
        return context

    @property
    def subject_visit_model_cls(self):
        return django_apps.get_model(settings.SUBJECT_VISIT_MODEL)

    @property
    def filter_by_visit_datetime(self) -> datetime | None:
        """Returns a datetime before which subjects are not included
        in the contact list.

        See get_queryset().
        """
        return getattr(settings, "EDC_RETINOPATHY_VISIT_DATETIME_FILTER", None)
