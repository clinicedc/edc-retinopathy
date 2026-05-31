from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning as CheckWarning


def storage_dir_check(**kwargs: object) -> list:  # noqa: ARG001
    """Django system check for EDC_RETINOPATHY_STORAGE_DIR configuration."""
    errors: list = []
    setting_value = getattr(settings, "EDC_RETINOPATHY_STORAGE_DIR", None)

    if not setting_value:
        errors.append(
            CheckWarning(
                "EDC_RETINOPATHY_STORAGE_DIR is not set.",
                hint=(
                    "Set EDC_RETINOPATHY_STORAGE_DIR in settings to the "
                    "base directory for retinal image storage."
                ),
                id="edc_retinopathy.W001",
            ),
        )
        return errors

    base = Path(setting_value).expanduser()

    if not base.is_dir():
        errors.append(
            Error(
                f"EDC_RETINOPATHY_STORAGE_DIR does not exist: {base}",
                hint="Create the directory or update the setting.",
                id="edc_retinopathy.E001",
            ),
        )
        return errors

    images_dir = base / "images"
    if not images_dir.is_dir():
        errors.append(
            Error(
                f"Missing 'images' subdirectory: {images_dir}",
                hint="Create the 'images/' subdirectory.",
                id="edc_retinopathy.E002",
            ),
        )

    return errors
