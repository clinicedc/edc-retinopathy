from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

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

# Columns read from RegisteredSubject
RS_FIELDS = (
    "id",
    "subject_identifier",
    "site_id",
    "gender",
    "dob",
)

AGREED_CHOICES = (YES, NO, NOT_APPLICABLE)

NOT_CONTACTED = "Not contacted"

AGREED_FILTER_CHOICES = (*AGREED_CHOICES, NOT_CONTACTED)

ANNOTATION_FIELDS = (
    "last_visit",
    "attempts",
    "agreed",
    "attend_date",
    "last_attempt",
    "call_list_pk",
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
        qs = RegisteredSubjectProxy.objects.exclude(has_eye_exam_register).annotate(
            last_visit=last_visit,
            attempts=F("call_list__number_of_attempts"),
            last_attempt=F("call_list__report_datetime"),
            call_list_pk=F("call_list__id"),
            attend_date=F("call_list__agreed_to_attend_date"),
            agreed=F("call_list__agreed_to_attend"),
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
        dte: datetime | None = getattr(settings, "EDC_RETINOPATHY_VISIT_DATETIME_FILTER", None)
        if dte:
            # keep the exact calendar year, month, and day, ignore offset
            return datetime.combine(dte.date(), time.min, tzinfo=ZoneInfo("UTC"))
        return None
