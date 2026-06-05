from clinicedc_constants import NOT_APPLICABLE, NULL_STRING
from clinicedc_constants.choices import YES_NO, YES_NO_NA
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from edc_model.models import BaseUuidModel, HistoricalRecords
from edc_prn.prn_model_manager import PrnModelManager
from edc_sites.managers import CurrentSiteManager
from edc_sites.model_mixins import SiteModelMixin

from .model_mixins import IdentityModelMixin
from .registered_subject_proxy import RegisteredSubjectProxy


class ContactAttempt(
    SiteModelMixin,
    IdentityModelMixin,
    BaseUuidModel,
):
    registered_subject = models.OneToOneField(
        RegisteredSubjectProxy,
        on_delete=models.PROTECT,
        related_name="contact_attempt",
    )

    report_datetime = models.DateTimeField(default=timezone.now)

    number_of_attempts = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )

    contact_made = models.CharField(
        verbose_name="Were you able to speak with the subject or their representative?",
        max_length=15,
        choices=YES_NO,
    )

    agreed_to_attend = models.CharField(
        "If contact made, has the subject agreed to attend the exam?",
        max_length=15,
        choices=YES_NO_NA,
        default=NOT_APPLICABLE,
    )

    agreed_to_attend_date = models.DateField(
        "Date the subject plans to attend the exam?",
        null=True,
        blank=True,
    )

    declined_reason = models.TextField(
        verbose_name="If the subject declined, give a brief reason why",
        default=NULL_STRING,
        blank=True,
    )

    objects = PrnModelManager()
    on_site = CurrentSiteManager()
    history = HistoricalRecords(inherit=True)

    class Meta(BaseUuidModel.Meta):
        verbose_name = "Contact Attempt"
        verbose_name_plural = "Contact Attempts"
