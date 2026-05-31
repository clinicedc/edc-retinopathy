from __future__ import annotations

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django_audit_fields import audit_fieldset_tuple
from edc_model_admin.dashboard import ModelAdminSubjectDashboardMixin
from edc_model_admin.history import SimpleHistoryAdmin
from rangefilter.filters import DateRangeFilterBuilder

from ..admin_site import edc_retinopathy_admin
from ..forms import CameraSessionForm
from ..models import CameraSession


@admin.register(CameraSession, site=edc_retinopathy_admin)
class CameraSessionAdmin(
    ModelAdminSubjectDashboardMixin,
    SimpleHistoryAdmin,
):
    form = CameraSessionForm

    show_object_tools: bool = True
    date_hierarchy = "created"

    autocomplete_fields = ("registered_subject",)

    list_display = (
        "subject_identifier",
        "eligible",
        "gender",
        "initials",
        "age_in_years",
        "report_datetime",
        "file_count",
        "device_id",
        "created",
    )
    list_filter = (("report_datetime", DateRangeFilterBuilder()), "device_id", "site")
    search_fields = ("registered_subject__subject_identifier",)

    fieldsets = (
        (
            "Session",
            {
                "fields": (
                    "registered_subject",
                    "report_datetime",
                    "report_type",
                    "device_id",
                ),
            },
        ),
        (
            "Contra-indication screening",
            {
                "description": (
                    "Document any contra-indications before proceeding "
                    "with retinal imaging. These responses are for "
                    "documentation only and do not block the session."
                ),
                "fields": (
                    "visual_impairment",
                    "retinal_conditions",
                    "ocular_interventions",
                    "photosensitive",
                    "pregnant",
                ),
            },
        ),
        audit_fieldset_tuple,
    )

    radio_fields = {  # noqa: RUF012
        "visual_impairment": admin.VERTICAL,
        "retinal_conditions": admin.VERTICAL,
        "ocular_interventions": admin.VERTICAL,
        "photosensitive": admin.VERTICAL,
        "pregnant": admin.VERTICAL,
        "report_type": admin.VERTICAL,
    }

    @admin.display(description="Files")
    def file_count(self, obj: CameraSession) -> str:
        count = obj.files.count()
        if not count:
            return self.empty_value_display
        url = reverse("edc_retinopathy_admin:edc_retinopathy_sessionfile_changelist")
        return format_html(
            '<a href="{}?session__id__exact={}">{}</a>',
            url,
            obj.pk,
            count,
        )

    @admin.display(description="Eligible", boolean=True)
    def eligible(self, obj: CameraSession) -> bool | None:
        if obj.contraindicated is not None:
            return not obj.contraindicated
        return obj.contraindicated
