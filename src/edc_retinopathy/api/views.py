from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CameraSession, SessionFile
from .serializers import FileUploadSerializer, ResolveSubjectSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# Magic bytes for basic content validation
_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF"
_HTML_MARKERS = (b"<!doctype", b"<html", b"<head", b"<body")

_VALID_FILE_TYPES = frozenset(
    {"left", "right", "report", "left_report", "right_report"},
)
_REPORT_FILE_TYPES = frozenset({"report", "left_report", "right_report"})
_IMAGE_FILE_TYPES = frozenset({"left", "right"})

# Default settings
_DEFAULT_MAX_FILE_SIZE_MB = 10
_DEFAULT_SESSION_EXPIRE_MINUTES = 120


def _get_max_file_size_bytes() -> int:
    mb = getattr(
        settings,
        "EDC_RETINOPATHY_MAX_FILE_SIZE_MB",
        _DEFAULT_MAX_FILE_SIZE_MB,
    )
    return int(mb * 1024 * 1024)


def _get_session_expire_minutes() -> int:
    return int(
        getattr(
            settings,
            "EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES",
            _DEFAULT_SESSION_EXPIRE_MINUTES,
        ),
    )


def _get_storage_dir() -> Path:
    base = Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser()
    return base / "images"


def _validate_subject_against_session(
    camera_session: CameraSession,
    initials: str,
    sex: str,
    age: int | None,
) -> dict:
    """Validate demographics from the camera against a CameraSession.

    The CameraSession is populated from RegisteredSubject when it is
    saved, so this cross-checks the camera's local DB against the EDC.

    Returns a dict with 'valid' (bool), 'code' (str), and
    'errors' (list of str).
    """
    errors: list[str] = []

    if camera_session.initials and camera_session.initials.upper() != initials.upper():
        errors.append(
            f"Initials mismatch: expected '{camera_session.initials}', got '{initials}'.",
        )
    if camera_session.gender and camera_session.gender.upper() != sex.upper():
        errors.append(
            f"Sex mismatch: expected '{camera_session.gender}', got '{sex}'.",
        )
    if (
        age is not None
        and camera_session.age_in_years is not None
        and abs(camera_session.age_in_years - age) > 1
    ):
        errors.append(
            f"Age mismatch: expected ~{camera_session.age_in_years}, got {age}.",
        )
    if errors:
        return {"valid": False, "code": "validation_mismatch", "errors": errors}
    return {"valid": True, "code": "ok", "errors": []}


def _validate_file_content(uploaded_file, file_type: str) -> str | None:
    """Basic magic-byte validation. Returns error message or None."""
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


def _image_response_data(session_file: SessionFile) -> dict:
    """Build the standard response payload for a SessionFile."""
    return {
        "id": str(session_file.pk),
        "camera_session_id": session_file.camera_session_id,
        "file_type": session_file.file_type,
        "original_filename": session_file.original_filename,
        "stored_filename": session_file.stored_filename,
        "checksum": session_file.checksum,
    }


def _find_camera_session(
    subject_identifier: str,
    camera_session_id: str | None = None,
) -> CameraSession | None:
    """Find an active session by subject_identifier.

    If camera_session_id is provided, look up that specific session (no expiry
    check — the caller explicitly chose it). Otherwise find the most
    recent non-expired session.
    """
    if camera_session_id is not None:
        return CameraSession.objects.filter(
            pk=camera_session_id,
            subject_identifier=subject_identifier,
        ).first()
    expire_minutes = _get_session_expire_minutes()
    cutoff = timezone.now() - timedelta(minutes=expire_minutes)
    return (
        CameraSession.objects.filter(
            subject_identifier=subject_identifier,
            report_datetime__gte=cutoff,
        )
        .order_by("-report_datetime")
        .first()
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
    """Resolve a subject identifier against an existing CameraSession.

    POST /api/retinopathy/resolve/

    A CameraSession must be created in the EDC by the clinician before
    the camera exam. This endpoint finds the most recent incomplete
    session for the subject, validates demographics from the camera's
    local DB, and returns the camera_session_id for file uploads.
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
        # Walk sessions newest-first; skip contraindicated and complete.
        qs: QuerySet[CameraSession] = CameraSession.objects.filter(
            subject_identifier=subject_identifier,
        ).order_by("-report_datetime")

        camera_session_obj = None
        for obj in qs:
            if obj.contraindicated:
                continue
            if obj.is_complete:
                continue
            camera_session_obj = obj
            break

        if camera_session_obj is None:
            # Distinguish "no camera_session_objs at all" from "all ineligible".
            if not qs.exists():
                logger.warning(
                    "No camera session for %s (device=%s). "
                    "Create one in the EDC before the exam.",
                    subject_identifier,
                    device_id,
                )
                return Response(
                    {
                        "code": "no_session",
                        "errors": [
                            "No camera session found for this subject. "
                            "Create one in the EDC before conducting "
                            "the exam.",
                        ],
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
                    "errors": [
                        "All sessions for this subject are complete or "
                        "contraindicated. Create a new camera session in the "
                        "EDC to upload again.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded = set(camera_session_obj.files.values_list("file_type", flat=True))

        # --- Validate demographics against session ---
        result = _validate_subject_against_session(
            camera_session=camera_session_obj,
            initials=data["initials"],
            sex=data["sex"],
            age=data.get("age"),
        )
        if not result["valid"]:
            logger.warning(
                "Resolve failed for %s session=%s (device=%s): %s",
                subject_identifier,
                camera_session_obj.pk,
                device_id,
                "; ".join(result["errors"]),
            )
            return Response(
                {"code": result["code"], "errors": result["errors"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Update device_id if the session doesn't have one ---
        if device_id and not camera_session_obj.device_id:
            camera_session_obj.device_id = device_id
            camera_session_obj.save(update_fields=["device_id"])

        logger.info(
            "Resolved session %s for %s (device=%s, uploaded=%s)",
            camera_session_obj.pk,
            subject_identifier,
            device_id,
            sorted(uploaded),
        )

        return Response(
            {
                "subject_identifier": camera_session_obj.subject_identifier,
                "camera_session_id": camera_session_obj.pk,
                "reactivated": bool(uploaded),
            },
            status=status.HTTP_200_OK,
        )


class SessionStatusView(APIView):
    """Return the current camera_session_obj status for a subject.

    GET /api/retinopathy/<subject_identifier>/status/
    Returns the most recent camera_session_obj and which file types have been received.
    """

    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(
        self,
        request: Request,  # noqa: ARG002
        subject_identifier: str,
    ) -> Response:
        camera_session_obj = (
            CameraSession.objects.filter(
                subject_identifier=subject_identifier,
            )
            .order_by("-report_datetime")
            .first()
        )
        if not camera_session_obj:
            return Response(
                {
                    "code": "no_session",
                    "error": "No session found for this subject.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded = set(camera_session_obj.files.values_list("file_type", flat=True))
        expected = camera_session_obj.expected_file_types

        return Response(
            {
                "camera_session_id": camera_session_obj.pk,
                "subject_identifier": camera_session_obj.subject_identifier,
                "report_datetime": camera_session_obj.report_datetime.isoformat(),
                "uploaded": sorted(uploaded),
                "missing": sorted(expected - uploaded),
                "complete": camera_session_obj.is_complete,
            },
            status=status.HTTP_200_OK,
        )


class FileUploadView(APIView):
    """Receive a file (left eye, right eye, or report) from the camera.

    POST /api/retinopathy/<subject_identifier>/left/
    POST /api/retinopathy/<subject_identifier>/right/
    POST /api/retinopathy/<subject_identifier>/report/

    Query params:
        camera_session_id (optional): Target a specific camera_session_obj instead of the
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

        # --- Find camera_session_obj (by explicit camera_session_id or most recent) ---
        camera_session_id = request.query_params.get("camera_session_id") or None

        camera_session_obj = _find_camera_session(
            subject_identifier,
            camera_session_id=camera_session_id,
        )
        if not camera_session_obj:
            expire_minutes = _get_session_expire_minutes()
            error_msg = "No active session found. Call resolve first."
            if camera_session_id:
                error_msg = (
                    f"Session {camera_session_id} not found for subject {subject_identifier}."
                )
            else:
                error_msg += f" Sessions expire after {expire_minutes} minutes."
            return Response(
                {"code": "no_session", "error": error_msg},
                status=status.HTTP_404_NOT_FOUND,
            )

        # --- Save new file atomically (before deleting old) ---
        ext = Path(uploaded_file.name).suffix.lower() or (
            ".pdf" if file_type == "report" else ".jpg"
        )
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        dest = _get_storage_dir() / stored_filename

        dest.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent), suffix=f".tmp{ext}")
        try:
            with os.fdopen(fd, "wb") as out:
                for chunk in uploaded_file.chunks():
                    out.write(chunk)
            os.rename(tmp_path, str(dest))  # noqa: PTH104
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)  # noqa: PTH108
            logger.exception(
                "Failed to write %s for %s session=%s",
                file_type,
                subject_identifier,
                camera_session_obj.pk,
            )
            return Response(
                {
                    "code": "storage_error",
                    "error": "File could not be saved to storage. Please retry the upload.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --- Replace existing record if re-uploaded ---
        existing = SessionFile.objects.filter(
            camera_session=camera_session_obj,
            file_type=file_type,
        ).first()
        if existing:
            # Remove old file from disk (new file is already safely written)
            old_path = _get_storage_dir() / existing.stored_filename
            with contextlib.suppress(OSError):
                old_path.unlink()
            logger.info(
                "Replacing %s for %s session=%s (old=%s)",
                file_type,
                subject_identifier,
                camera_session_obj.pk,
                existing.stored_filename,
            )
            existing.delete()

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
                camera_session_obj.pk,
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
            camera_session=camera_session_obj,
            file_type=file_type,
            original_filename=uploaded_file.name,
            stored_filename=stored_filename,
            file_content_type=uploaded_file.content_type or "",
            file_size=uploaded_file.size,
            capture_datetime=capture_datetime,
            checksum=stored_checksum,
        )

        logger.info(
            "Received %s for %s session=%s (%s bytes, stored=%s)",
            file_type,
            subject_identifier,
            camera_session_obj.pk,
            uploaded_file.size,
            stored_filename,
        )

        return Response(
            _image_response_data(session_file),
            status=status.HTTP_201_CREATED,
        )
