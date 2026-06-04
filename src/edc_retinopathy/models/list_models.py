from edc_list_data.model_mixins import ListModelMixin


class MissedReferralReasons(ListModelMixin):
    class Meta(ListModelMixin.Meta):
        verbose_name = "Missed Referral Reasons"
        verbose_name_plural = "Missed Referral Reasons"
