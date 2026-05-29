"""Django settings for running edc_retinopathy tests."""

import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "simple_history",
    "django_crypto_fields.apps.AppConfig",
    "django_revision.apps.AppConfig",
    "edc_consent.apps.AppConfig",
    "edc_device.apps.AppConfig",
    "edc_facility.apps.AppConfig",
    "edc_identifier.apps.AppConfig",
    "edc_metadata.apps.AppConfig",
    "edc_model.apps.AppConfig",
    "edc_notification.apps.AppConfig",
    "edc_prn.apps.AppConfig",
    "edc_protocol.apps.AppConfig",
    "edc_registration.apps.AppConfig",
    "edc_sites.apps.AppConfig",
    "edc_timepoint.apps.AppConfig",
    "edc_visit_schedule.apps.AppConfig",
    "edc_visit_tracking.apps.AppConfig",
    "rest_framework",
    "rest_framework.authtoken",
    "edc_retinopathy",
]

APP_NAME = "edc_retinopathy"

SITE_ID = 1

ROOT_URLCONF = "edc_retinopathy.tests.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

# edc-retinopathy settings
_STORAGE_TMP = Path(tempfile.mkdtemp(prefix="edc_retinopathy_test_"))
(_STORAGE_TMP / "images").mkdir(exist_ok=True)
EDC_RETINOPATHY_STORAGE_DIR = str(_STORAGE_TMP)

EDC_RETINOPATHY_MAX_FILE_SIZE_MB = 10
EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES = 120

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
}

USE_TZ = True
TIME_ZONE = "UTC"

DJANGO_REVISION_IGNORE_WORKING_DIR = True

EDC_SITES_REGISTER_DEFAULT = True
EDC_SITES_CREATE_DEFAULT = False

EDC_PROTOCOL_STUDY_OPEN_DATETIME = datetime(
    2019, 8, 1, 8, 0, tzinfo=ZoneInfo("UTC")
)
EDC_PROTOCOL_STUDY_CLOSE_DATETIME = datetime(
    2029, 8, 1, 8, 0, tzinfo=ZoneInfo("UTC")
)

SUBJECT_VISIT_MODEL = "edc_visit_tracking.subjectvisit"
SUBJECT_VISIT_MISSED_MODEL = "edc_visit_tracking.subjectvisitmissed"
SUBJECT_CONSENT_MODEL = "edc_consent.subjectconsent"
SUBJECT_SCREENING_MODEL = "edc_screening.subjectscreening"
SUBJECT_REQUISITION_MODEL = "edc_visit_tracking.subjectrequisition"

SILENCED_SYSTEM_CHECKS = [
    "edc_navbar.E002",
    "edc_navbar.E003",
    "edc_sites.E001",
]
