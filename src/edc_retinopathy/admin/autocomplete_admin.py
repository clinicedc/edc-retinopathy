from django.contrib import admin
from edc_registration.admin import RegisteredSubjectAdmin as BaseRegisteredSubjectAdmin

from ..admin_site import edc_retinopathy_admin
from ..models import RegisteredSubjectProxy


@admin.register(RegisteredSubjectProxy, site=edc_retinopathy_admin)
class RegisteredSubjectProxyAdmin(BaseRegisteredSubjectAdmin):
    """Registered again for the autocomplete field"""

    fieldsets = (
        (
            "Subject",
            {
                "fields": (
                    "subject_identifier",
                    "initials",
                    "dob",
                    "gender",
                ),
            },
        ),
    )

    list_display = (
        "subject_identifier",
        "initials",
        "dob",
        "gender",
    )
    search_fields = ("subject_identifier",)

    readonly_fields = ("subject_identifier",)

    radio_fields = {"gender": admin.HORIZONTAL}  # noqa: RUF012
