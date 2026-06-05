from __future__ import annotations

from clinicedc_constants import NOT_APPLICABLE, NOT_EVALUATED, NULL_STRING, YES
from clinicedc_constants.choices import YES_NO_NA, YES_NO_NOT_EVALUATED
from django.db import models
from django.utils import timezone
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
from .model_mixins import IdentityModelMixin
from .registered_subject_proxy import RegisteredSubjectProxy


class CameraSession(
    SiteModelMixin,
    IdentityModelMixin,
    BaseUuidModel,
):
    """Represents a single retinopathy exam for a subject.

    Completed by the clinic staff before the exam.
    """

    registered_subject = models.ForeignKey(
        RegisteredSubjectProxy,
        on_delete=models.PROTECT,
    )

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

    pregnant = models.CharField(
        verbose_name="Is the patient pregnant?",
        max_length=25,
        choices=YES_NO_NA,
        help_text="Not applicable for male patients.",
    )

    self_reported_impairment = models.CharField(
        verbose_name=(
            "Has the subject reported any issue with their "
            "eyes making them ineligible for retinopathy screening"
        ),
        max_length=25,
        choices=YES_NO_NOT_EVALUATED,
        default=NOT_EVALUATED,
        help_text="Self-reported",
    )

    visual_impairment = models.CharField(
        verbose_name=(
            "Does the patient have persistent visual impairment in one or both eyes?"
        ),
        max_length=25,
        choices=YES_NO_NOT_EVALUATED,
        default=NOT_EVALUATED,
        help_text="Self-reported or diagnosed.",
    )

    retinal_conditions = models.CharField(
        verbose_name="Does the patient have pre-existing retinal conditions?",
        max_length=25,
        choices=YES_NO_NOT_EVALUATED,
        default=NOT_EVALUATED,
        help_text=(
            "Such as macular edema, retinal vascular occlusion, "
            "or any form of retinopathy not related to diabetes."
        ),
    )

    ocular_interventions = models.CharField(
        verbose_name="Does the patient have a history of ocular interventions?",
        max_length=25,
        choices=YES_NO_NOT_EVALUATED,
        default=NOT_EVALUATED,
        help_text=(
            "Including retinal laser treatment, intravitreal injections, "
            "or intraocular surgeries (excluding uncomplicated cataract surgery)."
        ),
    )

    photosensitive = models.CharField(
        verbose_name=(
            "Is the patient photosensitive or otherwise contraindicated for retinal imaging?"
        ),
        max_length=25,
        choices=YES_NO_NOT_EVALUATED,
        default=NOT_EVALUATED,
    )

    op_comment = models.TextField(
        verbose_name="Ophthalmologist's comment", default=NULL_STRING
    )

    op_referral = models.CharField(
        verbose_name="Has the Ophthalmologist referred the subject for follow-up care?",
        choices=YES_NO_NA,
        max_length=15,
        default=NOT_APPLICABLE,
    )

    referred_to = models.CharField(
        verbose_name="If referred, name of facility subject referred",
        max_length=200,
        blank=True,
    )

    referred_date = models.DateField(
        verbose_name="If referred, date of referral",
        null=True,
        blank=True,
    )

    may_contact = models.CharField(
        verbose_name="If referred, may we contact the patient to followup on the referral?",
        max_length=15,
        choices=YES_NO_NA,
        default=NOT_APPLICABLE,
    )

    objects = PrnModelManager()
    on_site = CurrentSiteManager()
    history = HistoricalRecords(inherit=True)

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
