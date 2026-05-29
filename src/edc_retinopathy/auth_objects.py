from django.apps import apps as django_apps

RETINOPATHY = "RETINOPATHY"
RETINOPATHY_VIEW = "RETINOPATHY_VIEW"
RETINOPATHY_SUPER = "RETINOPATHY_SUPER"
EDC_RETINOPATHY = "edc_retinopathy"
EDC_RETINOPATHY_ROLE = "edc_retinopathy_role"

codenames = []
app_config = django_apps.get_app_config(EDC_RETINOPATHY)
for model_cls in app_config.get_models():
    if (
        "historical" not in model_cls._meta.label_lower
        and "registeredsubjectproxy" not in model_cls._meta.label_lower
    ):
        for action in ["view_", "add_", "change_", "delete_", "view_historical"]:
            codename = f".{action}".join(model_cls._meta.label_lower.split("."))
            codenames.append(codename)  # noqa: PERF401

codenames.append(f"{EDC_RETINOPATHY}.view_registeredsubjectproxy")
codenames.sort()
