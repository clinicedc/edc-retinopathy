from __future__ import annotations

from django.contrib import admin
from django_audit_fields import audit_fieldset_tuple
from edc_model_admin.dashboard import ModelAdminSubjectDashboardMixin
from edc_model_admin.history import SimpleHistoryAdmin
from rangefilter.filters import DateRangeFilterBuilder

from ..admin_site import edc_retinopathy_admin
from ..forms import ReferralFollowupForm
from ..models import ReferralFollowup


@admin.register(ReferralFollowup, site=edc_retinopathy_admin)
class ReferralFollowupAdmin(
    ModelAdminSubjectDashboardMixin,
    SimpleHistoryAdmin,
):
    form = ReferralFollowupForm

    show_object_tools: bool = True
    date_hierarchy = "created"

    autocomplete_fields = ("registered_subject",)

    list_display = (
        "subject_identifier",
        "gender",
        "initials",
        "report_datetime",
        "attended",
        "facility_attended",
        "attended_date",
        "created",
    )
    list_filter = (
        ("report_datetime", DateRangeFilterBuilder()),
        "attended",
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
                ),
            },
        ),
        (
            "Follow-up",
            {
                "fields": (
                    "attended",
                    "missed_referral_reasons",
                    "other_missed_referral_reason",
                    "facility_attended",
                    "attended_date",
                ),
            },
        ),
        audit_fieldset_tuple,
    )

    radio_fields = {  # noqa: RUF012
        "attended": admin.VERTICAL,
    }

    filter_horizontal = ("missed_referral_reasons",)
