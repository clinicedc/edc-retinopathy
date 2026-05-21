"""Minimal RegisteredSubject stand-in for tests.

The real RegisteredSubject lives in edc_registration which depends on
the full EDC stack. For isolated testing we define a lightweight model
with only the fields the retinopathy API actually queries.
"""

from __future__ import annotations

from django.db import models


class RegisteredSubject(models.Model):
    subject_identifier = models.CharField(max_length=50, unique=True)
    initials = models.CharField(max_length=10, blank=True, default="")
    gender = models.CharField(max_length=1, blank=True, default="")
    dob = models.DateField(null=True, blank=True)

    class Meta:
        app_label = "edc_retinopathy_tests"
