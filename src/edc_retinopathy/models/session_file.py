from __future__ import annotations

from django.db import models
from edc_model.models import BaseUuidModel, HistoricalRecords
from edc_prn.prn_model_manager import PrnModelManager

from ..choices import FILE_CONTENT_TYPE_CHOICES, FILE_TYPE_CHOICES


class SessionFile(BaseUuidModel):
    """Stores metadata for files received from the retinopathy camera.

    Each file is linked to a CameraSession and categorized as
    a left-eye image, right-eye image, or report (PDF or HTML).
    """

    camera_session = models.ForeignKey(
        "edc_retinopathy.CameraSession",
        on_delete=models.PROTECT,
        related_name="files",
    )

    file_type = models.CharField(
        max_length=20,
        choices=FILE_TYPE_CHOICES,
        help_text="Category: left eye, right eye, left/right report, or combined report.",
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

    file_content_type = models.CharField(
        verbose_name="content type",
        max_length=100,
        choices=FILE_CONTENT_TYPE_CHOICES,
        blank=True,
        default="",
        help_text="MIME type of the uploaded file.",
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

    objects = PrnModelManager()
    history = HistoricalRecords(inherit=True)

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.get_file_type_display()})"

    class Meta(BaseUuidModel.Meta):
        verbose_name = "Session file"
        verbose_name_plural = "Session files"
        constraints = (
            models.UniqueConstraint(
                fields=["camera_session", "original_filename"],
                name="unique_session_orig_filename",
            ),
        )
