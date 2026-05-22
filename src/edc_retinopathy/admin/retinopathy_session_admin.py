from __future__ import annotations

from django.contrib import admin

from ..models import RetinopathySession


@admin.register(RetinopathySession)
class RetinopathySessionAdmin(admin.ModelAdmin):
    list_display = [
        "subject_identifier",
        "initials",
        "sex",
        "age",
        "device_id",
        "site_id",
        "file_count",
        "created_datetime",
    ]
    list_filter = ["site_id", "device_id", "created_datetime"]
    search_fields = ["subject_identifier", "initials"]
    readonly_fields = [
        "id",
        "subject_identifier",
        "initials",
        "sex",
        "age",
        "device_id",
        "site_id",
        "created_datetime",
    ]
    date_hierarchy = "created_datetime"

    @admin.display(description="Files")
    def file_count(self, obj: RetinopathySession) -> int:
        return obj.files.count()

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
