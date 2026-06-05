from __future__ import annotations

from clinicedc_constants import YES
from django import forms
from edc_form_validators import FormValidator, FormValidatorMixin

from ..models import DmRetinopathyScreening


class DmRetinopathyScreeningValidator(FormValidator):
    def clean(self):
        # Rule 1: If either eye has macular involvement, DME must be Yes.
        od = self.cleaned_data.get("od_macular_involvement")
        os_ = self.cleaned_data.get("os_macular_involvement")
        dme = self.cleaned_data.get("dme_suspected")
        if (od == YES or os_ == YES) and dme != YES:
            self.raise_validation_error(
                {
                    "dme_suspected": (
                        "Expected Yes. Macular involvement is "
                        "indicated in at least one eye."
                    ),
                },
            )

        # Rule 2: If image quality is ungradable, force grade and action.
        image_quality = self.cleaned_data.get("image_quality")
        if image_quality == DmRetinopathyScreening.ImageQuality.UNGRADABLE:
            final_grade = self.cleaned_data.get("final_severity_grade")
            if final_grade != DmRetinopathyScreening.SeverityGrade.UNGRADABLE:
                self.raise_validation_error(
                    {
                        "final_severity_grade": (
                            "Expected 'Ungradable'. Image quality is "
                            "marked as ungradable."
                        ),
                    },
                )
            action = self.cleaned_data.get("recommended_action")
            if action != DmRetinopathyScreening.ActionPlan.RETAKE:
                self.raise_validation_error(
                    {
                        "recommended_action": (
                            "Expected 'Recall Patient for Re-imaging'. "
                            "Image quality is marked as ungradable."
                        ),
                    },
                )


class DmRetinopathyScreeningForm(FormValidatorMixin, forms.ModelForm):
    form_validator_cls = DmRetinopathyScreeningValidator

    class Meta:
        model = DmRetinopathyScreening
        fields = (
            "camera_session",
            "report_datetime",
            "interpreted_by",
            "image_quality",
            "limitation_cataract",
            "limitation_small_pupil",
            "limitation_artifact",
            "limitation_blur",
            "od_hemorrhages",
            "od_cotton_wool_spots",
            "od_irma_venous_beading",
            "od_neovascularization",
            "od_macular_involvement",
            "os_hemorrhages",
            "os_cotton_wool_spots",
            "os_irma_venous_beading",
            "os_neovascularization",
            "os_macular_involvement",
            "final_severity_grade",
            "dme_suspected",
            "recommended_action",
            "clinical_notes",
        )
