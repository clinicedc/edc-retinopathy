from clinicedc_constants.choices import YES_NO
from django.db import models
from django.utils import timezone
from edc_model.models import BaseUuidModel, HistoricalRecords
from edc_model_fields.fields import OtherCharField
from edc_prn.prn_model_manager import PrnModelManager
from edc_sites.managers import CurrentSiteManager
from edc_sites.model_mixins import SiteModelMixin

from .list_models import MissedReferralReasons
from .model_mixins import IdentityModelMixin
from .registered_subject_proxy import RegisteredSubjectProxy


class ReferralFollowup(SiteModelMixin, IdentityModelMixin, BaseUuidModel):
    registered_subject = models.ForeignKey(
        RegisteredSubjectProxy,
        on_delete=models.PROTECT,
        related_name="referral_followup",
    )
    report_datetime = models.DateTimeField(default=timezone.now)

    attended = models.CharField(
        verbose_name=(
            "Did you attend the health facility following referral from the META Trial"
        ),
        choices=YES_NO,
        max_length=25,
    )

    missed_referral_reasons = models.ManyToManyField(
        MissedReferralReasons,
        verbose_name=(
            "If 'No', please provide a reason for not seeking further care or follow up?"
        ),
        blank=True,
    )

    other_missed_referral_reason = OtherCharField(
        verbose_name="If other 'reason for not seeking further care', please specify ...",
        null=True,
        blank=True,
    )

    facility_attended = models.CharField(
        verbose_name="If 'Yes', please give the name of the facility you attended",
        max_length=50,
        default="",
        blank=True,
    )

    attended_date = models.DateField(
        verbose_name="What was the date you attended the health facility named above?",
        null=True,
        blank=True,
    )

    objects = PrnModelManager()
    on_site = CurrentSiteManager()
    history = HistoricalRecords(inherit=True)

    class Meta(BaseUuidModel.Meta):
        verbose_name = "Follow-up after referral"
        verbose_name_plural = "Follow-up after referral"
