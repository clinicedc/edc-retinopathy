from __future__ import annotations

from rest_framework import serializers

SEX_CHOICES = ("M", "F")


class UpperCaseChoiceField(serializers.ChoiceField):
    """ChoiceField that normalises input to uppercase before validation."""

    def to_internal_value(self, data: str) -> str:
        if isinstance(data, str):
            data = data.upper()
        return super().to_internal_value(data)


class ResolveSubjectSerializer(serializers.Serializer):
    """Validates the resolve-subject payload from the camera."""

    subject_identifier = serializers.CharField(max_length=50)
    initials = serializers.CharField(max_length=10)
    sex = UpperCaseChoiceField(choices=SEX_CHOICES)
    age = serializers.IntegerField(required=False, default=None)
    device_id = serializers.CharField(max_length=100, required=False, default="")
    site_id = serializers.CharField(max_length=50, required=False, default="")


class FileUploadSerializer(serializers.Serializer):
    """Validates the file upload payload (left eye, right eye, or report)."""

    file = serializers.FileField(help_text="The image or report file.")
    capture_datetime = serializers.DateTimeField(
        help_text="Capture timestamp as reported by the camera.",
    )
