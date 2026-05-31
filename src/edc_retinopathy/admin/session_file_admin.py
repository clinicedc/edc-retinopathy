from __future__ import annotations

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django_audit_fields import ModelAdminAuditFieldsMixin
from django_revision.modeladmin_mixin import ModelAdminRevisionMixin
from edc_model_admin.history import SimpleHistoryAdmin
from edc_model_admin.mixins import (
    ModelAdminFormAutoNumberMixin,
    ModelAdminFormInstructionsMixin,
    ModelAdminInstitutionMixin,
    ModelAdminNextUrlRedirectMixin,
    ModelAdminRedirectOnDeleteMixin,
    ModelAdminReplaceLabelTextMixin,
    TemplatesModelAdminMixin,
)
from edc_notification.modeladmin_mixins import NotificationModelAdminMixin

from ..admin_site import edc_retinopathy_admin
from ..constants import LEFT_REPORT, REPORT, RIGHT_REPORT
from ..models import SessionFile


@admin.register(SessionFile, site=edc_retinopathy_admin)
class SessionFileAdmin(
    TemplatesModelAdminMixin,
    ModelAdminNextUrlRedirectMixin,  # add
    NotificationModelAdminMixin,
    ModelAdminFormInstructionsMixin,  # add
    ModelAdminFormAutoNumberMixin,
    ModelAdminRevisionMixin,  # add
    ModelAdminInstitutionMixin,  # add
    ModelAdminRedirectOnDeleteMixin,
    ModelAdminReplaceLabelTextMixin,
    ModelAdminAuditFieldsMixin,
    SimpleHistoryAdmin,
):
    date_hierarchy = "modified"
    empty_value_display = "-"
    list_per_page = 10
    show_cancel = True

    list_display = (
        "original_filename",
        "file_type",
        "view_report_link",
        "session_link",
        "file_content_type",
        "file_size",
        "capture_datetime",
        "received_datetime",
    )
    list_filter = (
        "file_type",
        "file_content_type",
    )
    search_fields = (
        "original_filename",
        "camera_session__subject_identifier",
    )
    readonly_fields = (
        "id",
        "camera_session",
        "file_type",
        "original_filename",
        "stored_filename",
        "file_content_type",
        "file_size",
        "checksum",
        "capture_datetime",
        "received_datetime",
    )

    @admin.display(description="Session")
    def session_link(self, obj: SessionFile) -> str:
        url = reverse(
            "edc_retinopathy_admin:edc_retinopathy_camerasession_changelist",
        )
        return format_html(
            '<a href="{}?id__exact={}">{}</a>',
            url,
            obj.camera_session_id,
            obj.camera_session,
        )

    @admin.display(description="Report")
    def view_report_link(self, obj: SessionFile) -> str:
        report_types = {REPORT, LEFT_REPORT, RIGHT_REPORT}
        if obj.file_type not in report_types:
            return self.empty_value_display
        url = reverse("edc_retinopathy:report-view", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">View</a>', url)

    def has_add_permission(self, request: object) -> bool:  # noqa: ARG002
        return False

    def has_change_permission(
        self,
        request: object,  # noqa: ARG002
        obj: object = None,  # noqa: ARG002
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: object,  # noqa: ARG002
        obj: object = None,  # noqa: ARG002
    ) -> bool:
        return False
