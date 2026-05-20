from __future__ import annotations

from typing import ClassVar

from django.db import models


LEFT_EYE = "L"
RIGHT_EYE = "R"
BOTH_EYES = "B"

EYE_CHOICES = [
    (LEFT_EYE, "Left"),
    (RIGHT_EYE, "Right"),
    (BOTH_EYES, "Both"),
]


class RetinopathyResult(models.Model):
    """Stores analysis results received from the retinopathy camera."""

    subject_identifier = models.CharField(max_length=50, db_index=True)

    image_date = models.DateField(
        help_text="Date the image was captured, as reported by the camera.",
    )

    eye = models.CharField(
        max_length=1,
        choices=EYE_CHOICES,
        blank=True,
        default="",
        help_text="Which eye was imaged.",
    )

    grading = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Overall grading/classification from the camera software.",
    )

    analysis_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Raw analysis payload from the camera software. "
            "Schema TBD — will be refined once vendor provides sample JSON."
        ),
    )

    device_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Identifier for the camera device (for multi-site tracking).",
    )

    site_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Study site identifier.",
    )

    received_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-received_datetime"]
        verbose_name = "Retinopathy Result"
        verbose_name_plural = "Retinopathy Results"

    def __str__(self) -> str:
        return f"{self.subject_identifier} {self.image_date} {self.get_eye_display()}"
