from django.apps import AppConfig as DjangoAppConfig
from django.core.checks.registry import register

from .system_checks import storage_dir_check


class AppConfig(DjangoAppConfig):
    name = "edc_retinopathy"
    verbose_name = "Edc Retinopathy"
    include_in_administration_section = True
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        register(storage_dir_check)
