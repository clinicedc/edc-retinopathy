from edc_model_admin.admin_site import EdcAdminSite

from .apps import AppConfig

edc_retinopathy_admin = EdcAdminSite(
    name="edc_retinopathy_admin",
    app_label=AppConfig.name,
)
