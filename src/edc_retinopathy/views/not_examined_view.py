"""View listing registered subjects who have not had a camera session."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import Exists, F, OuterRef, QuerySet
from django.views.generic import ListView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin
from edc_utils import age, get_utcnow

from ..models import CameraSession, RegisteredSubjectProxy

# Only these columns are selected. RegisteredSubject carries six encrypted
# fields (first_name, last_name, full_name, familiar_name, initials, identity)
# and each one is decrypted per row when a model instance is materialized, so
# selecting values() keeps them out of the query entirely.
REPORT_VALUES = (
    "id",
    "subject_identifier",
    "gender",
    "dob",
    "attempts",
    "last_attempt",
    "contact_attempt_pk",
)


def _decorate(
    rows: list[dict[str, Any]],
    reference_dt: datetime | None = None,
) -> list[dict[str, Any]]:
    """Add `age_in_years` to each row for the template."""
    reference_dt = reference_dt or get_utcnow()
    for row in rows:
        row["age_in_years"] = age(row["dob"], reference_dt).years if row["dob"] else None
    return rows


class NotExaminedView(EdcViewMixin, NavbarViewMixin, ListView):
    """List registered subjects with no camera session.

    This is the outreach worklist that feeds `ContactAttempt`.
    """

    template_name = "edc_retinopathy/not_examined.html"
    context_object_name = "registered_subjects"
    navbar_selected_item = "edc_lab_results"

    def get_queryset(self) -> QuerySet[dict[str, Any]]:
        has_camera_session = Exists(
            CameraSession.objects.filter(registered_subject=OuterRef("pk")),
        )
        # Traversing the nullable reverse one-to-one is a LEFT JOIN, so subjects
        # never contacted annotate to None instead of raising DoesNotExist.
        return (
            RegisteredSubjectProxy.objects.exclude(has_camera_session)
            .annotate(
                attempts=F("contact_attempt__number_of_attempts"),
                last_attempt=F("contact_attempt__report_datetime"),
                contact_attempt_pk=F("contact_attempt__id"),
            )
            .values(*REPORT_VALUES)
            .order_by("subject_identifier")
        )

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        rows = _decorate(list(context["registered_subjects"]))
        context["registered_subjects"] = rows
        context["object_list"] = rows
        return context
