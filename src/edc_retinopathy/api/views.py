from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..dicom_preview import convert_dicom_to_jpeg
from ..models import EyeExamRegister, SessionFile
from ..utils import get_storage_dir
from .serializers import FileUploadSerializer, ResolveSubjectSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# Magic bytes for basic content validation
_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF"
_DICOM_MAGIC = b"DICM"  # at offset 128
_DICOM_PREAMBLE_LEN = 128
_HTML_MARKERS = (b"<!doctype", b"<html", b"<head", b"<body")

_VALID_FILE_TYPES = frozenset(
    {"left", "right", "report", "left_report", "right_report", "left_dicom", "right_dicom"},
)
_REPORT_FILE_TYPES = frozenset({"report", "left_report", "right_report"})
_IMAGE_FILE_TYPES = frozenset({"left", "right"})
_DICOM_FILE_TYPES = frozenset({"left_dicom", "right_dicom"})

# Default settings
_DEFAULT_MAX_FILE_SIZE_MB = 10


def _get_max_file_size_bytes() -> int:
    mb = getattr(
        settings,
        "EDC_RETINOPATHY_MAX_FILE_SIZE_MB",
        _DEFAULT_MAX_FILE_SIZE_MB,
    )
    return int(mb * 1024 * 1024)


def _validate_file_content(uploaded_file, file_type: str) -> str | None:
    """Basic magic-byte validation. Returns error message or None."""
    if file_type in _DICOM_FILE_TYPES:
        # DICOM: 128-byte preamble then "DICM"
        head = uploaded_file.read(_DICOM_PREAMBLE_LEN + 4)
        uploaded_file.seek(0)
        if len(head) < _DICOM_PREAMBLE_LEN + 4:
            return "File is too small to be a valid DICOM."
        if head[_DICOM_PREAMBLE_LEN:] != _DICOM_MAGIC:
            return "File does not appear to be a valid DICOM."
        return None
    head = uploaded_file.read(256)
    uploaded_file.seek(0)
    if not head:
        return "Uploaded file is empty."
    if file_type in _REPORT_FILE_TYPES:
        # Accept PDF or HTML for report types
        stripped = head.lstrip(b"\xef\xbb\xbf \t\n\r")
        is_pdf = stripped.startswith(_PDF_MAGIC)
        is_html = any(stripped.lower().startswith(m) for m in _HTML_MARKERS)
        if not (is_pdf or is_html):
            return "Report file does not appear to be a valid PDF or HTML."
    # Accept JPEG and PNG for eye images
    elif not (head.startswith(_JPEG_MAGIC) or head.startswith(b"\x89PNG")):
        return "Image file does not appear to be a valid JPEG or PNG."
    return None


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file on disk."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _compute_sha256_uploaded(uploaded_file) -> str:
    """Compute SHA-256 hex digest of an in-memory/temp uploaded file.

    Leaves the file position at 0 so it can still be written to disk
    afterwards.
    """
    h = hashlib.sha256()
    uploaded_file.seek(0)
    for chunk in uploaded_file.chunks():
        h.update(chunk)
    uploaded_file.seek(0)
    return h.hexdigest()


def _duplicate_upload_response(
    subject_identifier: str,
    file_type: str,
    eye_exam_register_obj: EyeExamRegister,
    uploaded_file,
) -> Response | None:
    """Handle a retry of a file already stored for this session.

    A retried upload (e.g. the client timed out waiting for a response
    that was in fact sent) would otherwise hit the unique constraint on
    (eye_exam_register, original_filename) and crash with an uncaught
    IntegrityError. Returns a Response if *uploaded_file* is a duplicate
    (identical or conflicting) of an existing SessionFile, else None.
    """
    existing = SessionFile.objects.filter(
        eye_exam_register=eye_exam_register_obj,
        original_filename=uploaded_file.name,
    ).first()
    if existing is None:
        return None

    incoming_checksum = _compute_sha256_uploaded(uploaded_file)
    if incoming_checksum == existing.checksum:
        logger.info(
            "Duplicate upload for %s/%s session=%s ignored (already stored, checksum match).",
            subject_identifier,
            file_type,
            eye_exam_register_obj.pk,
        )
        return Response(_image_response_data(existing), status=status.HTTP_200_OK)

    logger.warning(
        "Filename conflict for %s/%s session=%s: '%s' already stored "
        "with a different checksum.",
        subject_identifier,
        file_type,
        eye_exam_register_obj.pk,
        uploaded_file.name,
    )
    return Response(
        {
            "code": "filename_conflict",
            "error": (
                f"A file named '{uploaded_file.name}' was already "
                "uploaded for this session with different content."
            ),
        },
        status=status.HTTP_409_CONFLICT,
    )


def _image_response_data(session_file: SessionFile) -> dict:
    """Build the standard response payload for a SessionFile."""
    return {
        "id": str(session_file.pk),
        "eye_exam_register_id": session_file.eye_exam_register_id,
        "file_type": session_file.file_type,
        "original_filename": session_file.original_filename,
        "stored_filename": session_file.stored_filename,
        "checksum": session_file.checksum,
    }


def _find_eye_exam_register(
    subject_identifier: str,
    eye_exam_register_id: str | None = None,
) -> EyeExamRegister | None:
    """Find a session by subject_identifier.

    If eye_exam_register_id is provided, look up that specific session.
    Otherwise find the most recent session for the subject.
    """
    if eye_exam_register_id is not None:
        return EyeExamRegister.objects.filter(
            pk=eye_exam_register_id,
            subject_identifier=subject_identifier,
        ).first()
    return (
        EyeExamRegister.objects.filter(
            subject_identifier=subject_identifier,
        )
        .order_by("-report_datetime")
        .first()
    )


def _resolve_eye_exam_register_or_error(
    subject_identifier: str,
    eye_exam_register_id: str | None,
) -> tuple[EyeExamRegister | None, Response | None]:
    """Resolve the target EyeExamRegister, or build a 404 error Response."""
    eye_exam_register_obj = _find_eye_exam_register(
        subject_identifier,
        eye_exam_register_id=eye_exam_register_id,
    )
    if eye_exam_register_obj:
        return eye_exam_register_obj, None
    if eye_exam_register_id:
        error_msg = (
            f"Session {eye_exam_register_id} not found for subject {subject_identifier}."
        )
    else:
        error_msg = (
            f"No session found for subject {subject_identifier}. "
            "Create a EyeExamRegister in the EDC first."
        )
    return None, Response(
        {"code": "no_session", "error": error_msg},
        status=status.HTTP_404_NOT_FOUND,
    )


def _server_error_response(message: str) -> Response:
    """Return a 500 response with Retry-After header."""
    response = Response(
        {"code": "server_error", "error": message},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    response["Retry-After"] = "30"
    return response


class PingView(APIView):
    """Health-check endpoint for the camera to verify connectivity.

    GET /api/retinopathy/ping/
    Returns 200 with {"status": "ok"} if the server and auth are working.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:  # noqa ARG002
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ResolveSubjectView(APIView):
    """Confirm that a EyeExamRegister exists for a subject.

    POST /api/retinopathy/resolve/

    A EyeExamRegister must be created in the EDC by the clinician before
    the camera exam.  This endpoint confirms that at least one eligible
    (non-complete, non-contraindicated) session exists and returns its
    ``eye_exam_register_id``.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    def post(self, request: Request) -> Response:
        serializer = ResolveSubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subject_identifier = data["subject_identifier"]
        device_id = data.get("device_id", "")

        # --- Find the most recent eligible session ---
        qs: QuerySet[EyeExamRegister] = EyeExamRegister.objects.filter(
            subject_identifier=subject_identifier,
        ).order_by("-report_datetime")

        eye_exam_register_obj = None
        for obj in qs:
            if obj.contraindicated:
                continue
            if obj.is_complete:
                continue
            eye_exam_register_obj = obj
            break

        if eye_exam_register_obj is None:
            if not qs.exists():
                logger.warning(
                    "No entry in the Eye Exam Registerf for %s (device=%s). "
                    "Create one in the EDC before the exam.",
                    subject_identifier,
                    device_id,
                )
                return Response(
                    {
                        "code": "no_session",
                        "error": (
                            "No entry found in the Eye Exam Register for this subject. "
                            "Create one in the EDC before conducting "
                            "the exam."
                        ),
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            logger.warning(
                "All sessions for %s are complete or contraindicated (device=%s).",
                subject_identifier,
                device_id,
            )
            return Response(
                {
                    "code": "no_eligible_session",
                    "error": (
                        "All sessions for this subject are complete or "
                        "contraindicated. Create a new entry in the Eye Exam Register "
                        "to upload again."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Update device_id if the session doesn't have one ---
        if device_id and not eye_exam_register_obj.device_id:
            eye_exam_register_obj.device_id = device_id
            eye_exam_register_obj.save(update_fields=["device_id"])

        uploaded = sorted(
            eye_exam_register_obj.files.values_list("file_type", flat=True),
        )

        logger.info(
            "Resolved session %s for %s (device=%s, uploaded=%s)",
            eye_exam_register_obj.pk,
            subject_identifier,
            device_id,
            uploaded,
        )

        return Response(
            {
                "subject_identifier": eye_exam_register_obj.subject_identifier,
                "eye_exam_register_id": eye_exam_register_obj.pk,
                "uploaded": uploaded,
            },
            status=status.HTTP_200_OK,
        )


class SessionStatusView(APIView):
    """Return the current eye_exam_register_obj status for a subject.

    GET /api/retinopathy/<subject_identifier>/status/
    Returns the most recent eye_exam_register_obj and which file types have been received.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(
        self,
        request: Request,  # noqa: ARG002
        subject_identifier: str,
    ) -> Response:
        eye_exam_register_obj = (
            EyeExamRegister.objects.filter(
                subject_identifier=subject_identifier,
            )
            .order_by("-report_datetime")
            .first()
        )
        if not eye_exam_register_obj:
            return Response(
                {
                    "code": "no_session",
                    "error": "No session found for this subject.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded = set(eye_exam_register_obj.files.values_list("file_type", flat=True))
        expected = eye_exam_register_obj.expected_file_types

        return Response(
            {
                "eye_exam_register_id": eye_exam_register_obj.pk,
                "subject_identifier": eye_exam_register_obj.subject_identifier,
                "report_datetime": eye_exam_register_obj.report_datetime.isoformat(),
                "uploaded": sorted(uploaded),
                "missing": sorted(expected - uploaded),
                "complete": eye_exam_register_obj.is_complete,
            },
            status=status.HTTP_200_OK,
        )


class FileUploadView(APIView):
    """Receive a file (left eye, right eye, or report) from the camera.

    POST /api/retinopathy/<subject_identifier>/left/
    POST /api/retinopathy/<subject_identifier>/right/
    POST /api/retinopathy/<subject_identifier>/report/

    Query params:
        eye_exam_register_id (optional): Target a specific eye_exam_register_obj instead of the
            most recent one. Useful after reconnection.

    Body: multipart/form-data with 'file', 'capture_datetime', and
    optional 'checksum' (SHA-256 hex digest) fields.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(  # noqa: PLR0911
        self,
        request: Request,
        subject_identifier: str,
        file_type: str,
    ) -> Response:
        if file_type not in _VALID_FILE_TYPES:
            return Response(
                {
                    "code": "invalid_file_type",
                    "error": f"Invalid file type: '{file_type}'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        capture_datetime = serializer.validated_data["capture_datetime"]
        checksum = serializer.validated_data.get("checksum", "")

        # --- File size check ---
        max_size = _get_max_file_size_bytes()
        if uploaded_file.size > max_size:
            max_mb = max_size / (1024 * 1024)
            logger.warning(
                "File too large for %s/%s: %s bytes (max %s MB)",
                subject_identifier,
                file_type,
                uploaded_file.size,
                max_mb,
            )
            return Response(
                {
                    "code": "file_too_large",
                    "error": (
                        f"File size {uploaded_file.size} bytes exceeds "
                        f"maximum of {max_mb:.0f} MB."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Content validation ---
        content_error = _validate_file_content(uploaded_file, file_type)
        if content_error:
            logger.warning(
                "Content validation failed for %s/%s: %s",
                subject_identifier,
                file_type,
                content_error,
            )
            return Response(
                {"code": "invalid_content", "error": content_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Find eye_exam_register_obj (by explicit eye_exam_register_id or most recent) ---
        eye_exam_register_id = request.query_params.get("eye_exam_register_id") or None

        eye_exam_register_obj, error_response = _resolve_eye_exam_register_or_error(
            subject_identifier,
            eye_exam_register_id,
        )
        if error_response is not None:
            return error_response

        # --- Idempotency check: has this exact file already been received? ---
        duplicate_response = _duplicate_upload_response(
            subject_identifier,
            file_type,
            eye_exam_register_obj,
            uploaded_file,
        )
        if duplicate_response is not None:
            return duplicate_response

        # --- Save file under session subdirectory with original filename ---
        session_dir = get_storage_dir() / str(eye_exam_register_obj.pk)
        session_dir.mkdir(parents=True, exist_ok=True)
        original_filename = uploaded_file.name
        stored_filename = f"{eye_exam_register_obj.pk}/{original_filename}"
        dest = session_dir / original_filename

        fd, tmp_path = tempfile.mkstemp(
            dir=str(session_dir),
            suffix=f".tmp{Path(original_filename).suffix.lower()}",
        )
        try:
            with os.fdopen(fd, "wb") as out:
                for chunk in uploaded_file.chunks():
                    out.write(chunk)
            Path(tmp_path).rename(dest)
        except OSError:
            with contextlib.suppress(OSError):
                Path(tmp_path).unlink()
            logger.exception(
                "Failed to write %s for %s session=%s",
                file_type,
                subject_identifier,
                eye_exam_register_obj.pk,
            )
            return Response(
                {
                    "code": "storage_error",
                    "error": "File could not be saved to storage. Please retry the upload.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --- Compute SHA-256 of stored file (used for verification and response) ---
        stored_checksum = _compute_sha256(dest)

        if checksum and stored_checksum != checksum.lower():
            # Delete the corrupt file
            with contextlib.suppress(OSError):
                dest.unlink()
            logger.warning(
                "Checksum mismatch for %s/%s session=%s: expected %s, got %s",
                subject_identifier,
                file_type,
                eye_exam_register_obj.pk,
                checksum.lower(),
                stored_checksum,
            )
            return Response(
                {
                    "code": "checksum_mismatch",
                    "error": (
                        "File integrity check failed. "
                        f"Expected SHA-256 {checksum}, "
                        f"got {stored_checksum}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session_file = SessionFile.objects.create(
            eye_exam_register=eye_exam_register_obj,
            file_type=file_type,
            original_filename=uploaded_file.name,
            stored_filename=stored_filename,
            file_content_type=uploaded_file.content_type or "",
            file_size=uploaded_file.size,
            capture_datetime=capture_datetime,
            checksum=stored_checksum,
        )

        # --- Generate JPEG preview for DICOM files (best effort) ---
        if file_type in _DICOM_FILE_TYPES:
            try:
                preview_name = f"{dest.stem}_preview.jpg"
                preview_path = dest.parent / "previews" / preview_name
                if convert_dicom_to_jpeg(dest, preview_path):
                    session_file.preview_filename = (
                        f"{eye_exam_register_obj.pk}/previews/{preview_name}"
                    )
                    session_file.save(update_fields=["preview_filename"])
            except Exception:  # noqa: BLE001
                logger.exception(
                    "DICOM preview generation failed for %s session=%s — "
                    "upload accepted without preview",
                    subject_identifier,
                    eye_exam_register_obj.pk,
                )

        logger.info(
            "Received %s for %s session=%s (%s bytes, stored=%s)",
            file_type,
            subject_identifier,
            eye_exam_register_obj.pk,
            uploaded_file.size,
            stored_filename,
        )

        return Response(
            _image_response_data(session_file),
            status=status.HTTP_201_CREATED,
        )
