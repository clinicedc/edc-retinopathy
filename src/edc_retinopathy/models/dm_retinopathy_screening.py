from clinicedc_constants.choices import (
    YES_NO_NOT_EVALUATED,
)
from django.db import models
from django.utils import timezone
from edc_model.models import BaseUuidModel, HistoricalRecords
from edc_prn.prn_model_manager import PrnModelManager
from edc_sites.managers import CurrentSiteManager
from edc_sites.model_mixins import SiteModelMixin

from edc_retinopathy.models import CameraSession


def evaluation_fields_factory_mixin(laterality: str) -> type[models.Model]:

    class AbstractModel(models.Model):
        class Meta:
            abstract = True

    class HemorrhageSeverity(models.TextChoices):
        NONE = "NONE", "None"
        MILD = "MILD", "Mild (< 20 overall)"
        SEVERE = "SEVERE", "Severe (>= 20 in at least one quadrant)"
        NOT_EVALUATED = "Not evaluated"

    label = laterality.upper()
    attrs = {
        f"{laterality}_hemorrhages": models.CharField(
            max_length=25,
            choices=HemorrhageSeverity.choices,
            verbose_name=f"{label} Microaneurysms / Hemorrhages",
            blank=False,
        ),
        f"{laterality}_cotton_wool_spots": models.CharField(
            verbose_name=f"{label} Cotton Wool Spots",
            max_length=20,
            choices=YES_NO_NOT_EVALUATED,
        ),
        f"{laterality}_irma_venous_beading": models.CharField(
            verbose_name=f"{label} IRMA / Venous Beading",
            max_length=20,
            choices=YES_NO_NOT_EVALUATED,
        ),
        f"{laterality}_neovascularization": models.CharField(
            verbose_name=f"{label} Neovascularization / Vitreous Hemorrhage",
            max_length=20,
            choices=YES_NO_NOT_EVALUATED,
        ),
        f"{laterality}_macular_involvement": models.CharField(
            verbose_name=f"{label} Macular Involvement",
            max_length=20,
            choices=YES_NO_NOT_EVALUATED,
            help_text=(
                "Hard lipid exudates or hemorrhages within 1 disc diameter of foveal center"
            ),
        ),
    }

    for name, fld_cls in attrs.items():
        AbstractModel.add_to_class(name, fld_cls)
    return AbstractModel


class DmRetinopathyScreening(
    evaluation_fields_factory_mixin("od"),
    evaluation_fields_factory_mixin("os"),
    SiteModelMixin,
    BaseUuidModel,
):
    """
    Stores data from a remote or image-only diabetic retinopathy screening
    conducted exclusively via fundus camera photographs.
    """

    class ImageQuality(models.TextChoices):
        EXCELLENT = "EXCELLENT", "Excellent / Clear Media"
        ACCESSIBLE = "ACCESSIBLE", "Acceptable for Diagnostic Evaluation"
        UNGRADABLE = "UNGRADABLE", "Ungradable / Insufficient Quality"
        NOT_EVALUATED = "Not evaluated"

    class SeverityGrade(models.TextChoices):
        NONE = "NONE", "No Retinopathy"
        MILD_NPDR = "MILD_NPDR", "Mild Non-Proliferative DR (Microaneurysms only)"
        MODERATE_NPDR = "MODERATE_NPDR", "Moderate Non-Proliferative DR"
        SEVERE_NPDR = "SEVERE_NPDR", "Severe Non-Proliferative DR (Meets 4-2-1 Rule)"
        PDR = "PDR", "Proliferative Diabetic Retinopathy (Neovascularization)"
        UNGRADABLE = "UNGRADABLE", "Ungradable"
        NOT_EVALUATED = "Not evaluated"

    class ActionPlan(models.TextChoices):
        ROUTINE_SCREEN = "ROUTINE", "Routine Rescreen in 12 Months"
        EARLY_RESCREEN = "EARLY", "Early Rescreen in 6 Months"
        REFERRAL = "REFERRAL", "Referral to Retina Specialist"
        RETAKE = "RETAKE", "Recall Patient for Re-imaging"
        NOT_EVALUATED = "Not evaluated"

    # --- Metadata & Auditing ---
    camera_session = models.OneToOneField(CameraSession, on_delete=models.PROTECT)

    report_datetime = models.DateTimeField(default=timezone.now)

    subject_identifier = models.CharField(max_length=50, null=True, editable=False)

    interpreted_by = models.CharField(
        max_length=150, help_text="Name or ID of the reading Ophthalmologist"
    )

    # --- Section 1: Image Quality Assessment ---
    image_quality = models.CharField(
        max_length=20, choices=ImageQuality.choices, default=ImageQuality.ACCESSIBLE
    )
    limitation_cataract = models.CharField(
        verbose_name="Cataract / Media Opacity",
        max_length=20,
        choices=YES_NO_NOT_EVALUATED,
    )
    limitation_small_pupil = models.CharField(
        verbose_name="Poor Dilation / Small Pupil",
        max_length=20,
        choices=YES_NO_NOT_EVALUATED,
    )
    limitation_artifact = models.CharField(
        verbose_name="Artifact (Blink, dust, glare)",
        max_length=20,
        choices=YES_NO_NOT_EVALUATED,
    )
    limitation_blur = models.CharField(
        verbose_name="Motion Blur / Poor Focus",
        max_length=20,
        choices=YES_NO_NOT_EVALUATED,
    )

    # --- Section 2: Right Eye (OD) Evaluation ---
    # see evaluation_fields_factory_mixin("od")

    # --- Section 3: Left Eye (OS) Evaluation ---
    # see evaluation_fields_factory_mixin("os")

    # --- Section 4: Final Screen Output & Clinical Action Plan ---

    final_severity_grade = models.CharField(
        max_length=20,
        choices=SeverityGrade.choices,
        help_text="Overall classification based on the worst-performing eye",
    )

    dme_suspected = models.CharField(
        verbose_name="Diabetic Macular Edema Suspected",
        max_length=20,
        choices=YES_NO_NOT_EVALUATED,
        help_text=(
            "Automatically flagged Yes if macular involvement is checked in either eye"
        ),
    )

    recommended_action = models.CharField(max_length=15, choices=ActionPlan.choices)

    clinical_notes = models.TextField(
        blank=True,
        help_text="Optional diagnostic narrative annotations",
    )

    objects = PrnModelManager()
    on_site = CurrentSiteManager()
    history = HistoricalRecords(inherit=True)

    def __str__(self):
        return (
            f"{self.camera_session.subject_identifier} - "
            f"Grade: {self.get_final_severity_grade_display()}"
        )

    def save(self, *args, **kwargs):
        self.subject_identifier = self.camera_session.subject_identifier
        super().save(*args, **kwargs)

    class Meta(BaseUuidModel.Meta):
        ordering = ("-report_datetime",)
        verbose_name = "Diabetic Retinopathy Screening"
        verbose_name_plural = "Diabetic Retinopathy Screenings"
