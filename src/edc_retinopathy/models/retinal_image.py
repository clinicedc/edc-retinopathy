from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

LEFT_EYE = "left"
RIGHT_EYE = "right"
REPORT = "report"

FILE_TYPE_CHOICES = [
    (LEFT_EYE, "Left eye"),
    (RIGHT_EYE, "Right eye"),
    (REPORT, "Report"),
]


class RetinalImage(models.Model):
    """Stores metadata for files received from the retinopathy camera.

    Each file is linked to a RetinopathySession and categorised as
    a left-eye image, right-eye image, or report PDF.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    session = models.ForeignKey(
        "edc_retinopathy.RetinopathySession",
        on_delete=models.PROTECT,
        related_name="files",
    )

    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        help_text="Category of this file: left eye, right eye, or report.",
    )

    original_filename = models.CharField(
        max_length=255,
        help_text="Original filename as sent by the camera software.",
    )

    stored_filename = models.CharField(
        max_length=255,
        unique=True,
        help_text="UUID-based filename used on disk.",
    )

    content_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="MIME type of the uploaded file (e.g. image/jpeg, application/pdf).",
    )

    file_size = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes.",
    )

    checksum = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="SHA-256 hex digest of the stored file.",
    )

    capture_datetime = models.DateTimeField(
        help_text="Capture timestamp as reported by the camera.",
    )

    received_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-received_datetime"]
        verbose_name = "Retinal Image"
        verbose_name_plural = "Retinal Images"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "file_type"],
                name="unique_session_file_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.get_file_type_display()})"
