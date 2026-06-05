"""Convert DICOM files to JPEG previews for browser viewing."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image
from pydicom import dcmread
from pydicom.errors import InvalidDicomError

logger = logging.getLogger(__name__)


def convert_dicom_to_jpeg(dicom_path: Path, output_path: Path) -> bool:
    """Convert a DICOM file to a JPEG preview image.

    Returns True on success, False on failure.
    """
    try:
        ds = dcmread(dicom_path)
        pixel_array = ds.pixel_array
    except (InvalidDicomError, AttributeError, ValueError):
        logger.exception("Failed to read DICOM pixel data: %s", dicom_path)
        return False

    # Normalize pixel data to 8-bit for JPEG
    arr = pixel_array.astype(np.float64)
    if arr.max() > arr.min():
        arr = (arr - arr.min()) / (arr.max() - arr.min()) * 255.0
    arr = arr.astype(np.uint8)

    # Handle color vs grayscale
    if arr.ndim == 2:
        img = Image.fromarray(arr, mode="L")
    elif arr.ndim == 3 and arr.shape[2] == 3:  # noqa: PLR2004
        img = Image.fromarray(arr, mode="RGB")
    else:
        # Unexpected shape — try as grayscale
        img = Image.fromarray(arr.squeeze(), mode="L")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=90)
    logger.info("Created DICOM preview: %s", output_path)
    return True
