from __future__ import annotations

from django.contrib import admin

from ..models import RetinalImage


@admin.register(RetinalImage)
class RetinalImageAdmin(admin.ModelAdmin):
    list_display = [
        "original_filename",
        "file_type",
        "session",
        "content_type",
        "file_size",
        "received_datetime",
    ]
    list_filter = ["file_type", "content_type"]
    search_fields = ["original_filename", "session__subject_identifier"]
    readonly_fields = [
        "id",
        "session",
        "file_type",
        "original_filename",
        "stored_filename",
        "content_type",
        "file_size",
        "received_datetime",
    ]

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
