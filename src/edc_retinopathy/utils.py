from pathlib import Path

from django.conf import settings


def get_storage_dir() -> Path:
    return Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser() / "images"
