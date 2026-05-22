from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "edc_retinopathy.tests"
    label = "edc_retinopathy_tests"
    verbose_name = "Edc Retinopathy Tests"
    default_auto_field = "django.db.models.BigAutoField"
