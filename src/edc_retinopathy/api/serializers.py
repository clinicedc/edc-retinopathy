from __future__ import annotations

from rest_framework import serializers


class ResolveSubjectSerializer(serializers.Serializer):
    """Validates the resolve-subject payload from the camera."""

    subject_identifier = serializers.CharField(max_length=50)
    initials = serializers.CharField(max_length=10, required=False, default="")
    sex = serializers.CharField(max_length=10, required=False, default="")
    age = serializers.IntegerField(required=False, default=None)
    device_id = serializers.CharField(max_length=100, required=False, default="")
    site_id = serializers.CharField(max_length=50, required=False, default="")


class FileUploadSerializer(serializers.Serializer):
    """Validates the file upload payload (left eye, right eye, or report)."""

    file = serializers.FileField(help_text="The image or report file.")
