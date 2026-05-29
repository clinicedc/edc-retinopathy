import sys
import tempfile
from pathlib import Path

from clinicedc_tests.config import DefaultTestSettings, get_installed_apps_for_tests

app_name = "edc_retinopathy"
base_dir = Path(__file__).absolute().parent.parent

_STORAGE_TMP = Path(tempfile.mkdtemp(prefix="edc_retinopathy_test_"))
(_STORAGE_TMP / "images").mkdir(exist_ok=True)

project_settings = DefaultTestSettings(
    calling_file=__file__,
    BASE_DIR=base_dir,
    APP_NAME=app_name,
    SILENCED_SYSTEM_CHECKS=[
        "sites.E101",
        "edc_sites.E001",
        "edc_sites.E002",
        "edc_navbar.E003",
        "edc_navbar.E004",
        "edc_consent.E001",
    ],
    INSTALLED_APPS=[
        *get_installed_apps_for_tests(
            "clinicedc_tests",
            "rest_framework",
            "rest_framework.authtoken",
            f"{app_name}.apps.AppConfig",
        ),
    ],
    add_dashboard_middleware=True,
    add_lab_dashboard_middleware=True,
    DJANGO_REVISION_IGNORE_WORKING_DIR=True,
    EDC_RETINOPATHY_STORAGE_DIR=str(_STORAGE_TMP),
    EDC_RETINOPATHY_MAX_FILE_SIZE_MB=10,
    EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES=120,
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.TokenAuthentication",
        ],
    },
).settings

for k, v in project_settings.items():
    setattr(sys.modules[__name__], k, v)
