from __future__ import annotations

from django.contrib import admin
from django_audit_fields import audit_fieldset_tuple
from edc_model_admin.dashboard import ModelAdminSubjectDashboardMixin
from edc_model_admin.history import SimpleHistoryAdmin
from rangefilter.filters import DateRangeFilterBuilder

from ..admin_site import edc_retinopathy_admin
from ..forms import ContactAttemptForm
from ..models import ContactAttempt


@admin.register(ContactAttempt, site=edc_retinopathy_admin)
class ContactAttemptAdmin(
    ModelAdminSubjectDashboardMixin,
    SimpleHistoryAdmin,
):
    form = ContactAttemptForm

    show_object_tools: bool = True
    date_hierarchy = "created"

    autocomplete_fields = ("registered_subject",)

    list_display = (
        "subject_identifier",
        "gender",
        "initials",
        "report_datetime",
        "number_of_attempts",
        "contact_made",
        "agreed_to_attend",
        "created",
    )
    list_filter = (
        ("report_datetime", DateRangeFilterBuilder()),
        "contact_made",
        "agreed_to_attend",
        "site",
    )
    search_fields = ("registered_subject__subject_identifier",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "registered_subject",
                    "report_datetime",
                    "number_of_attempts",
                ),
            },
        ),
        (
            "Contact outcome",
            {
                "fields": (
                    "contact_made",
                    "agreed_to_attend",
                    "agreed_to_attend_datetime",
                    "declined_reason",
                ),
            },
        ),
        audit_fieldset_tuple,
    )

    radio_fields = {  # noqa: RUF012
        "contact_made": admin.VERTICAL,
        "agreed_to_attend": admin.VERTICAL,
    }
