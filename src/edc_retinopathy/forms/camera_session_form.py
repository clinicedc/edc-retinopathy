from __future__ import annotations

from clinicedc_constants import FEMALE, MALE, NOT_APPLICABLE
from django import forms

from ..models import CameraSession


class CameraSessionForm(forms.ModelForm):
    def clean(self) -> dict:
        cleaned_data = super().clean()
        registered_subject = cleaned_data.get("registered_subject")
        if not registered_subject:
            self.add_error("registered_subject", "This field is required.")
        else:
            gender = registered_subject.gender
            pregnant = cleaned_data.get("pregnant", "")
            if gender == MALE and pregnant and pregnant != NOT_APPLICABLE:
                self.add_error(
                    "pregnant",
                    "This field is NOT applicable for male patients.",
                )
            if gender == FEMALE and pregnant == NOT_APPLICABLE:
                self.add_error(
                    "pregnant",
                    "This field is applicable for female patients.",
                )
        return cleaned_data

    class Meta:
        model = CameraSession
        fields = "__all__"
