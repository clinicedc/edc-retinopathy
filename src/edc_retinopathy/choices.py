from .constants import (
    APPLICATION_DICOM,
    APPLICATION_PDF,
    IMAGE_JPEG,
    IMAGE_PNG,
    LEFT_DICOM,
    LEFT_EYE,
    LEFT_REPORT,
    REPORT,
    REPORT_TYPE_COMBINED,
    REPORT_TYPE_PER_EYE,
    RIGHT_DICOM,
    RIGHT_EYE,
    RIGHT_REPORT,
    TEXT_HTML,
)

FILE_TYPE_CHOICES = [
    (LEFT_EYE, "Left eye"),
    (RIGHT_EYE, "Right eye"),
    (LEFT_DICOM, "Left eye DICOM"),
    (RIGHT_DICOM, "Right eye DICOM"),
    (LEFT_REPORT, "Left eye report"),
    (RIGHT_REPORT, "Right eye report"),
    (REPORT, "Report"),
]

REPORT_TYPE_CHOICES = [
    (REPORT_TYPE_COMBINED, "Combined (one report for both eyes)"),
    (REPORT_TYPE_PER_EYE, "Per eye (one report per eye)"),
]

FILE_CONTENT_TYPE_CHOICES = [
    (IMAGE_JPEG, "JPEG image"),
    (IMAGE_PNG, "PNG image"),
    (APPLICATION_PDF, "PDF document"),
    (APPLICATION_DICOM, "DICOM file"),
    (TEXT_HTML, "HTML document"),
]
