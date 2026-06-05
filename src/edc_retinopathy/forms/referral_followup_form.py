from __future__ import annotations

from clinicedc_constants import NO, OTHER, YES
from django import forms
from edc_form_validators import FormValidator, FormValidatorMixin

from ..models import ReferralFollowup


class ReferralFollowupValidator(FormValidator):
    def clean(self):
        self.required_if(
            YES,
            field="attended",
            field_required="facility_attended",
        )
        self.required_if(
            NO,
            field="attended",
            field_required="missed_referral_reasons",
        )
        self.required_if_m2m(
            OTHER,
            field="missed_referral_reasons",
            field_required="other_missed_referral_reason",
        )
        self.required_if(
            YES,
            field="attended",
            field_required="attended_date",
        )


class ReferralFollowupForm(FormValidatorMixin, forms.ModelForm):
    form_validator_cls = ReferralFollowupValidator

    class Meta:
        model = ReferralFollowup
        fields = (
            "registered_subject",
            "report_datetime",
            "attended",
            "missed_referral_reasons",
            "other_missed_referral_reason",
            "facility_attended",
            "attended_date",
        )
