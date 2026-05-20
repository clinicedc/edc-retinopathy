from __future__ import annotations

from django.contrib import admin

from ..models import RetinopathyResult


@admin.register(RetinopathyResult)
class RetinopathyResultAdmin(admin.ModelAdmin):
    list_display = [
        "subject_identifier",
        "image_date",
        "eye",
        "grading",
        "device_id",
        "site_id",
        "received_datetime",
    ]
    list_filter = ["eye", "site_id", "device_id", "image_date"]
    search_fields = ["subject_identifier", "grading"]
    readonly_fields = [
        "subject_identifier",
        "image_date",
        "eye",
        "grading",
        "analysis_data",
        "device_id",
        "site_id",
        "received_datetime",
    ]
    date_hierarchy = "image_date"

    def has_add_permission(self, request: object) -> bool:  # noqa: ARG002
        return False

    def has_change_permission(
        self, request: object, obj: object = None  # noqa: ARG002
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: object, obj: object = None  # noqa: ARG002
    ) -> bool:
        return False
