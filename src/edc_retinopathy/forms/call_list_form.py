from __future__ import annotations

from clinicedc_constants import NO, YES
from django import forms
from edc_form_validators import FormValidator, FormValidatorMixin

from ..models import CallList


class CallListValidator(FormValidator):
    def clean(self):
        self.applicable_if(
            YES,
            field="contact_made",
            field_applicable="agreed_to_attend",
        )
        self.required_if(
            YES,
            field="agreed_to_attend",
            field_required="agreed_to_attend_date",
        )
        self.required_if(
            NO,
            field="agreed_to_attend",
            field_required="declined_reason",
        )


class CallListForm(FormValidatorMixin, forms.ModelForm):
    form_validator_cls = CallListValidator

    class Meta:
        model = CallList
        fields = (
            "registered_subject",
            "report_datetime",
            "number_of_attempts",
            "contact_made",
            "agreed_to_attend",
            "agreed_to_attend_date",
            "declined_reason",
        )
