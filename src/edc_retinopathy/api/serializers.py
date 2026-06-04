from __future__ import annotations

from rest_framework import serializers


class ResolveSubjectSerializer(serializers.Serializer):
    """Validates the resolve-subject payload from the camera.

    Only the subject_identifier is required.  The server confirms
    that a CameraSession exists for this subject.
    """

    subject_identifier = serializers.CharField(max_length=50)
    device_id = serializers.CharField(max_length=100, required=False, default="")


class FileUploadSerializer(serializers.Serializer):
    """Validates the file upload payload (left eye, right eye, or report)."""

    file = serializers.FileField(help_text="The image or report file.")
    capture_datetime = serializers.DateTimeField(
        help_text="Capture timestamp as reported by the camera.",
    )
    checksum = serializers.CharField(
        max_length=64,
        required=False,
        default="",
        help_text="SHA-256 hex digest of the file for integrity verification.",
    )
