from __future__ import annotations

from clinicedc_constants import NOT_APPLICABLE, YES
from clinicedc_constants.choices import GENDER, YES_NO, YES_NO_NA
from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone
from django_crypto_fields.fields import EncryptedCharField
from edc_identifier.model_mixins import NonUniqueSubjectIdentifierFieldMixin
from edc_model.models import BaseUuidModel, HistoricalRecords
from edc_prn.prn_model_manager import PrnModelManager
from edc_sites.managers import CurrentSiteManager
from edc_sites.model_mixins import SiteModelMixin

from ..choices import REPORT_TYPE_CHOICES
from ..constants import (
    LEFT_EYE,
    LEFT_REPORT,
    REPORT,
    REPORT_TYPE_COMBINED,
    REPORT_TYPE_PER_EYE,
    RIGHT_EYE,
    RIGHT_REPORT,
)
from .registered_subject_proxy import RegisteredSubjectProxy


class CameraSession(
    SiteModelMixin, NonUniqueSubjectIdentifierFieldMixin, BaseUuidModel
):
    """Represents a single retinopathy camera session for a subject.

    Completed by the user before the exam.
    """

    registered_subject = models.ForeignKey(
        RegisteredSubjectProxy, on_delete=models.PROTECT
    )

    subject_identifier = models.CharField(max_length=50, null=True, editable=False)
    initials = EncryptedCharField(null=True, editable=False)
    age_in_years = models.IntegerField(null=True, editable=False)
    gender = models.CharField(max_length=10, choices=GENDER, null=True, editable=False)

    report_datetime = models.DateTimeField(default=timezone.now)

    device_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Identifier for the camera device.",
    )

    report_type = models.CharField(
        verbose_name="Report type",
        max_length=25,
        choices=REPORT_TYPE_CHOICES,
        default=REPORT_TYPE_COMBINED,
    )

    visual_impairment = models.CharField(
        verbose_name=(
            "Does the patient have persistent visual impairment in one or both eyes?"
        ),
        max_length=25,
        choices=YES_NO,
        help_text="Self-reported or diagnosed.",
    )

    retinal_conditions = models.CharField(
        verbose_name="Does the patient have pre-existing retinal conditions?",
        max_length=25,
        choices=YES_NO,
        help_text=(
            "Such as macular edema, retinal vascular occlusion, "
            "or any form of retinopathy not related to diabetes."
        ),
    )

    ocular_interventions = models.CharField(
        verbose_name="Does the patient have a history of ocular interventions?",
        max_length=25,
        choices=YES_NO,
        help_text=(
            "Including retinal laser treatment, intravitreal injections, "
            "or intraocular surgeries (excluding uncomplicated cataract surgery)."
        ),
    )

    photosensitive = models.CharField(
        verbose_name=(
            "Is the patient photosensitive or otherwise "
            "contraindicated for retinal imaging?"
        ),
        max_length=25,
        choices=YES_NO,
    )

    pregnant = models.CharField(
        verbose_name="Is the patient pregnant?",
        max_length=25,
        choices=YES_NO_NA,
        default=NOT_APPLICABLE,
        help_text="Not applicable for male patients.",
    )

    objects = PrnModelManager()
    on_site = CurrentSiteManager()
    history = HistoricalRecords(inherit=True)

    def __str__(self):
        return str(self.registered_subject)

    def save(self, *args, **kwargs):
        self.subject_identifier = self.registered_subject.subject_identifier
        self.gender = self.registered_subject.gender
        self.initials = self.registered_subject.initials
        self.age_in_years = abs(
            relativedelta(timezone.now().date(), self.registered_subject.dob).years
        )
        return super().save(*args, **kwargs)

    def natural_key(self):
        return (self.registered_subject.subject_identifier,)

    @property
    def expected_file_types(self) -> frozenset[str]:
        """Return the set of file types required for this session."""
        if self.report_type == REPORT_TYPE_PER_EYE:
            return frozenset({LEFT_EYE, RIGHT_EYE, LEFT_REPORT, RIGHT_REPORT})
        return frozenset({LEFT_EYE, RIGHT_EYE, REPORT})

    @property
    def is_complete(self) -> bool:
        """Return True if all expected files have been uploaded."""
        uploaded = set(self.files.values_list("file_type", flat=True))
        return self.expected_file_types.issubset(uploaded)

    @property
    def contraindicated(self) -> bool | None:
        """Return True if any contra-indication is YES, None if unanswered."""
        answers = [
            self.visual_impairment,
            self.retinal_conditions,
            self.ocular_interventions,
            self.photosensitive,
            self.pregnant,
        ]
        if not any(answers):
            return None
        return YES in answers

    class Meta(BaseUuidModel.Meta):
        verbose_name = "Camera Session"
        verbose_name_plural = "Camera Sessions"
