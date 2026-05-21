from __future__ import annotations

from typing import ClassVar

from django.db import models


class RetinopathySession(models.Model):
    """Represents a single retinopathy camera encounter for a subject.

    Created when the camera resolves a subject identifier. All uploaded
    files (left eye, right eye, report) are linked to this session.
    """

    subject_identifier = models.CharField(max_length=50, db_index=True)

    initials = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Subject initials as sent by the camera.",
    )

    sex = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="Sex as sent by the camera.",
    )

    age = models.IntegerField(
        null=True,
        blank=True,
        help_text="Age in years as sent by the camera.",
    )

    device_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Identifier for the camera device.",
    )

    site_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Study site identifier.",
    )

    created_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering: ClassVar = ["-created_datetime"]
        verbose_name = "Retinopathy Session"
        verbose_name_plural = "Retinopathy Sessions"

    def __str__(self) -> str:
        return f"{self.subject_identifier} {self.created_datetime:%Y-%m-%d %H:%M}"
