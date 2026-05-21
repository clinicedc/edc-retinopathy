"""Minimal Django settings for running edc_retinopathy tests in isolation."""

import tempfile
from pathlib import Path

SECRET_KEY = "test-secret-key-not-for-production"

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "rest_framework.authtoken",
    "edc_retinopathy.tests.apps.TestAppConfig",
    "edc_retinopathy",
]

ROOT_URLCONF = "edc_retinopathy.tests.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# edc-retinopathy settings
_STORAGE_TMP = Path(tempfile.mkdtemp(prefix="edc_retinopathy_test_"))
(_STORAGE_TMP / "images").mkdir(exist_ok=True)
EDC_RETINOPATHY_STORAGE_DIR = str(_STORAGE_TMP)

# Points to the test stand-in model
EDC_REGISTRATION_REGISTERED_SUBJECT_MODEL = (
    "edc_retinopathy_tests.registeredsubject"
)

EDC_RETINOPATHY_MAX_FILE_SIZE_MB = 10
EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES = 120

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
}

USE_TZ = True
TIME_ZONE = "UTC"
