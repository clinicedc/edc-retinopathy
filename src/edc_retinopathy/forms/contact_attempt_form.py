from __future__ import annotations

from clinicedc_constants import NO, YES
from django import forms
from edc_form_validators import FormValidator, FormValidatorMixin

from ..models import ContactAttempt


class ContactAttemptValidator(FormValidator):
    def clean(self):
        self.required_if(
            YES,
            field="contact_made",
            field_required="agreed_to_attend",
        )
        self.required_if(
            YES,
            field="agreed_to_attend",
            field_required="agreed_to_attend_datetime",
        )
        self.required_if(
            NO,
            field="agreed_to_attend",
            field_required="declined_reason",
        )


class ContactAttemptForm(FormValidatorMixin, forms.ModelForm):
    form_validator_cls = ContactAttemptValidator

    class Meta:
        model = ContactAttempt
        fields = (
            "registered_subject",
            "report_datetime",
            "number_of_attempts",
            "contact_made",
            "agreed_to_attend",
            "agreed_to_attend_datetime",
            "declined_reason",
        )
