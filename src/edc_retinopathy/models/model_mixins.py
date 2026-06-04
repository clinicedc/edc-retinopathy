from clinicedc_constants.choices import GENDER
from dateutil.relativedelta import relativedelta
from django.db import models
from django.utils import timezone
from django_crypto_fields.fields import EncryptedCharField


class IdentityModelMixin(models.Model):
    """Requires an FK to registered_subject."""

    subject_identifier = models.CharField(max_length=50, null=True, editable=False)
    initials = EncryptedCharField(null=True, editable=False)
    age_in_years = models.IntegerField(null=True, editable=False)
    gender = models.CharField(max_length=10, choices=GENDER, null=True, editable=False)

    def __str__(self):
        return str(self.registered_subject)

    def save(self, *args, **kwargs):
        self.subject_identifier = self.registered_subject.subject_identifier
        self.gender = self.registered_subject.gender
        self.initials = self.registered_subject.initials
        self.age_in_years = abs(
            relativedelta(timezone.now().date(), self.registered_subject.dob).years,
        )
        return super().save(*args, **kwargs)

    def natural_key(self):
        return (self.registered_subject.subject_identifier,)

    class Meta:
        abstract = True
