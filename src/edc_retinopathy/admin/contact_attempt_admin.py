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
        "report_datetime",
        "initials",
        "gender",
        "attempts",
        "contact",
        "will_attend",
        "appt_date",
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
                    "agreed_to_attend_date",
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

    @admin.display(description="Attempts")
    def attempts(self, obj: ContactAttempt):
        return obj.number_of_attempts

    @admin.display(description="Contact made")
    def contact(self, obj: ContactAttempt):
        return obj.contact_made

    @admin.display(description="Agreed to attend")
    def will_attend(self, obj: ContactAttempt):
        return obj.agreed_to_attend

    @admin.display(description="Appt date")
    def appt_date(self, obj: ContactAttempt):
        return obj.agreed_to_attend_date
