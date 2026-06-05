"""Tests for ContactAttempt and ReferralFollowup form validators."""

from __future__ import annotations

import contextlib
from copy import deepcopy

from clinicedc_constants import NO, NOT_APPLICABLE, OTHER, YES
from django import forms
from django.test import TestCase
from django.utils import timezone

from edc_retinopathy.forms.contact_attempt_form import ContactAttemptValidator
from edc_retinopathy.forms.referral_followup_form import ReferralFollowupValidator
from edc_retinopathy.models import (
    ContactAttempt,
    MissedReferralReasons,
    ReferralFollowup,
)

from .mixins import RetinopathyTestCaseMixin


class ContactAttemptFormTests(RetinopathyTestCaseMixin):
    """Tests for ContactAttemptValidator."""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.data = {
            "registered_subject": self.rs,
            "report_datetime": timezone.now(),
            "number_of_attempts": 1,
            "contact_made": YES,
            "agreed_to_attend": YES,
            "agreed_to_attend_date": timezone.now().date(),
            "declined_reason": "",
        }

    def _validate(self, data: dict) -> dict:
        form = ContactAttemptValidator(
            cleaned_data=data,
            model=ContactAttempt,
        )
        with contextlib.suppress(forms.ValidationError):
            form.validate()
        return form._errors

    def test_valid_contact_made_agreed(self) -> None:
        """Contact made and agreed to attend with date is valid."""
        errors = self._validate(self.data)
        self.assertEqual(errors, {})

    def test_contact_made_requires_agreed_to_attend(self) -> None:
        """If contact_made=YES, agreed_to_attend is required."""
        data = deepcopy(self.data)
        data["agreed_to_attend"] = ""
        errors = self._validate(data)
        self.assertIn("agreed_to_attend", errors)

    def test_agreed_to_attend_requires_datetime(self) -> None:
        """If agreed_to_attend=YES, agreed_to_attend_date is required."""
        data = deepcopy(self.data)
        data["agreed_to_attend_date"] = None
        errors = self._validate(data)
        self.assertIn("agreed_to_attend_date", errors)

    def test_declined_requires_reason(self) -> None:
        """If agreed_to_attend=NO, declined_reason is required."""
        data = deepcopy(self.data)
        data["agreed_to_attend"] = NO
        data["agreed_to_attend_date"] = None
        data["declined_reason"] = ""
        errors = self._validate(data)
        self.assertIn("declined_reason", errors)

    def test_declined_with_reason_valid(self) -> None:
        """Declined with a reason is valid."""
        data = deepcopy(self.data)
        data["agreed_to_attend"] = NO
        data["agreed_to_attend_date"] = None
        data["declined_reason"] = "Unable to travel"
        errors = self._validate(data)
        self.assertEqual(errors, {})

    def test_no_contact_made(self) -> None:
        """No contact made — agreed_to_attend must be not applicable."""
        data = deepcopy(self.data)
        data["contact_made"] = NO
        data["agreed_to_attend"] = NOT_APPLICABLE
        data["agreed_to_attend_date"] = None
        data["declined_reason"] = ""
        errors = self._validate(data)
        self.assertEqual(errors, {})


class ReferralFollowupFormTests(RetinopathyTestCaseMixin):
    """Tests for ReferralFollowupValidator."""

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        MissedReferralReasons.objects.get_or_create(
            name="cost",
            defaults={"display_name": "Cost of transport"},
        )
        MissedReferralReasons.objects.get_or_create(
            name=OTHER,
            defaults={"display_name": "Other"},
        )
        MissedReferralReasons.objects.get_or_create(
            name=NOT_APPLICABLE,
            defaults={"display_name": "Not applicable"},
        )

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.data = {
            "registered_subject": self.rs,
            "report_datetime": timezone.now(),
            "attended": YES,
            "missed_referral_reasons": MissedReferralReasons.objects.none(),
            "other_missed_referral_reason": "",
            "facility_attended": "District Hospital",
            "attended_date": timezone.now().date(),
        }

    def _validate(self, data: dict) -> dict:
        form = ReferralFollowupValidator(
            cleaned_data=data,
            model=ReferralFollowup,
        )
        with contextlib.suppress(forms.ValidationError):
            form.validate()
        return form._errors

    def test_valid_attended(self) -> None:
        """Attended with facility and date is valid."""
        errors = self._validate(self.data)
        self.assertEqual(errors, {})

    def test_attended_requires_facility(self) -> None:
        """If attended=YES, facility_attended is required."""
        data = deepcopy(self.data)
        data["facility_attended"] = ""
        errors = self._validate(data)
        self.assertIn("facility_attended", errors)

    def test_attended_requires_date(self) -> None:
        """If attended=YES, attended_date is required."""
        data = deepcopy(self.data)
        data["attended_date"] = None
        errors = self._validate(data)
        self.assertIn("attended_date", errors)

    def test_not_attended_requires_reasons(self) -> None:
        """If attended=NO, missed_referral_reasons is required."""
        data = deepcopy(self.data)
        data["attended"] = NO
        data["facility_attended"] = ""
        data["attended_date"] = None
        errors = self._validate(data)
        self.assertIn("missed_referral_reasons", errors)

    def test_not_attended_with_reasons_valid(self) -> None:
        """Not attended with a reason is valid."""
        data = deepcopy(self.data)
        data["attended"] = NO
        data["facility_attended"] = ""
        data["attended_date"] = None
        data["missed_referral_reasons"] = MissedReferralReasons.objects.filter(
            name="cost",
        )
        errors = self._validate(data)
        self.assertEqual(errors, {})

    def test_other_reason_requires_specify(self) -> None:
        """If missed_referral_reasons includes OTHER, specify is required."""
        data = deepcopy(self.data)
        data["attended"] = NO
        data["facility_attended"] = ""
        data["attended_date"] = None
        data["missed_referral_reasons"] = MissedReferralReasons.objects.filter(
            name=OTHER,
        )
        data["other_missed_referral_reason"] = ""
        errors = self._validate(data)
        self.assertIn("other_missed_referral_reason", errors)

    def test_other_reason_with_specify_valid(self) -> None:
        """OTHER with specify text is valid."""
        data = deepcopy(self.data)
        data["attended"] = NO
        data["facility_attended"] = ""
        data["attended_date"] = None
        data["missed_referral_reasons"] = MissedReferralReasons.objects.filter(
            name=OTHER,
        )
        data["other_missed_referral_reason"] = "No one to accompany me"
        errors = self._validate(data)
        self.assertEqual(errors, {})
