from __future__ import annotations

from django.contrib import admin
from django_audit_fields import audit_fieldset_tuple
from edc_model_admin.dashboard import ModelAdminSubjectDashboardMixin
from edc_model_admin.history import SimpleHistoryAdmin
from rangefilter.filters import DateRangeFilterBuilder

from ..admin_site import edc_retinopathy_admin
from ..forms import DmRetinopathyScreeningForm
from ..models import DmRetinopathyScreening


@admin.register(DmRetinopathyScreening, site=edc_retinopathy_admin)
class DmRetinopathyScreeningAdmin(ModelAdminSubjectDashboardMixin, SimpleHistoryAdmin):
    form = DmRetinopathyScreeningForm

    show_object_tools: bool = True
    date_hierarchy = "created"
    autocomplete_fields = ("camera_session",)

    list_display = (
        "camera_session",
        "report_datetime",
        "image_quality",
        "final_severity_grade",
        "dme_suspected",
        "recommended_action",
        "interpreted_by",
        "created",
    )
    list_filter = (
        ("report_datetime", DateRangeFilterBuilder()),
        "image_quality",
        "final_severity_grade",
        "recommended_action",
        "dme_suspected",
        "site",
    )
    search_fields = (
        "camera_session__subject_identifier",
        "interpreted_by",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "camera_session",
                    "report_datetime",
                    "interpreted_by",
                ),
            },
        ),
        (
            "Image quality assessment",
            {
                "fields": (
                    "image_quality",
                    "limitation_cataract",
                    "limitation_small_pupil",
                    "limitation_artifact",
                    "limitation_blur",
                ),
            },
        ),
        (
            "Right eye (OD) evaluation",
            {
                "fields": (
                    "od_hemorrhages",
                    "od_cotton_wool_spots",
                    "od_irma_venous_beading",
                    "od_neovascularization",
                    "od_macular_involvement",
                ),
            },
        ),
        (
            "Left eye (OS) evaluation",
            {
                "fields": (
                    "os_hemorrhages",
                    "os_cotton_wool_spots",
                    "os_irma_venous_beading",
                    "os_neovascularization",
                    "os_macular_involvement",
                ),
            },
        ),
        (
            "Final assessment and clinical action",
            {
                "fields": (
                    "final_severity_grade",
                    "dme_suspected",
                    "recommended_action",
                    "clinical_notes",
                ),
            },
        ),
        audit_fieldset_tuple,
    )

    radio_fields = {  # noqa: RUF012
        "image_quality": admin.VERTICAL,
        "limitation_cataract": admin.VERTICAL,
        "limitation_small_pupil": admin.VERTICAL,
        "limitation_artifact": admin.VERTICAL,
        "limitation_blur": admin.VERTICAL,
        "od_hemorrhages": admin.VERTICAL,
        "od_cotton_wool_spots": admin.VERTICAL,
        "od_irma_venous_beading": admin.VERTICAL,
        "od_neovascularization": admin.VERTICAL,
        "od_macular_involvement": admin.VERTICAL,
        "os_hemorrhages": admin.VERTICAL,
        "os_cotton_wool_spots": admin.VERTICAL,
        "os_irma_venous_beading": admin.VERTICAL,
        "os_neovascularization": admin.VERTICAL,
        "os_macular_involvement": admin.VERTICAL,
        "final_severity_grade": admin.VERTICAL,
        "dme_suspected": admin.VERTICAL,
        "recommended_action": admin.VERTICAL,
    }
