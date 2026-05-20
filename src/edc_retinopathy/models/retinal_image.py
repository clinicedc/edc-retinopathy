from __future__ import annotations

import uuid
from typing import ClassVar

from django.db import models

from .retinopathy_result import EYE_CHOICES


class RetinalImage(models.Model):
    """Stores metadata for retinal image files received from the camera."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    result = models.ForeignKey(
        "edc_retinopathy.RetinopathyResult",
        on_delete=models.PROTECT,
        related_name="images",
    )

    eye = models.CharField(
        max_length=1,
        choices=EYE_CHOICES,
        help_text="Which eye this image is for.",
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
        help_text="MIME type of the uploaded image (e.g. image/jpeg).",
    )

    file_size = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes.",
    )

    received_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-received_datetime"]
        verbose_name = "Retinal Image"
        verbose_name_plural = "Retinal Images"

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.get_eye_display()})"
