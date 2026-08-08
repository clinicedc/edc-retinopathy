from __future__ import annotations

from datetime import date

from clinicedc_constants import NO, NOT_APPLICABLE
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.test import TestCase
from django.utils import timezone
from edc_registration.models import RegisteredSubject
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from edc_retinopathy.constants import REPORT_TYPE_COMBINED
from edc_retinopathy.models import EyeExamRegister


class RetinopathyTestCaseMixin(TestCase):
    """Common setup for edc_retinopathy API tests."""

    @classmethod
    def setUpTestData(cls) -> None:
        Site.objects.get_or_create(
            id=settings.SITE_ID,
            defaults={"domain": "localhost", "name": "Test Site"},
        )

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(username="camera", password="pw")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def create_registered_subject(
        self,
        subject_identifier: str = "105-10-0001-2",
        initials: str = "JD",
        gender: str = "M",
        dob: date | None = None,
    ) -> RegisteredSubject:
        if dob is None:
            dob = date(1990, 6, 15)
        return RegisteredSubject.objects.create(
            subject_identifier=subject_identifier,
            initials=initials,
            gender=gender,
            dob=dob,
        )

    def create_eye_exam_register(
        self,
        registered_subject: RegisteredSubject,
        report_type: str = REPORT_TYPE_COMBINED,
        **kwargs,
    ) -> EyeExamRegister:
        defaults = {
            "registered_subject": registered_subject,
            "report_datetime": timezone.now(),
            "report_type": report_type,
            "visual_impairment": NO,
            "retinal_conditions": NO,
            "ocular_interventions": NO,
            "photosensitive": NO,
            "pregnant": NOT_APPLICABLE,
            "site_id": settings.SITE_ID,
        }
        defaults.update(kwargs)
        return EyeExamRegister.objects.create(**defaults)
