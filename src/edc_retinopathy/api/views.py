from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import uuid
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import RetinalImage, RetinopathySession
from .serializers import FileUploadSerializer, ResolveSubjectSerializer

logger = logging.getLogger(__name__)

# Magic bytes for basic content validation
_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF"

# Default settings
_DEFAULT_MAX_FILE_SIZE_MB = 10
_DEFAULT_SESSION_EXPIRE_MINUTES = 120
_DEFAULT_SESSION_REACTIVATION_HOURS = 24


def _get_max_file_size_bytes() -> int:
    mb = getattr(settings, "EDC_RETINOPATHY_MAX_FILE_SIZE_MB", _DEFAULT_MAX_FILE_SIZE_MB)
    return int(mb * 1024 * 1024)


def _get_session_expire_minutes() -> int:
    return int(
        getattr(
            settings,
            "EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES",
            _DEFAULT_SESSION_EXPIRE_MINUTES,
        )
    )


def _get_session_reactivation_hours() -> int:
    return int(
        getattr(
            settings,
            "EDC_RETINOPATHY_SESSION_REACTIVATION_HOURS",
            _DEFAULT_SESSION_REACTIVATION_HOURS,
        )
    )


def _get_storage_dir() -> Path:
    base = Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser()
    return base / "images"


def _get_registered_subject_model():
    from django.apps import apps

    return apps.get_model(settings.EDC_REGISTRATION_REGISTERED_SUBJECT_MODEL)


def _validate_subject(
    subject_identifier: str,
    initials: str,
    sex: str,
    age: int | None,
) -> dict:
    """Validate subject against RegisteredSubject.

    Returns a dict with 'valid' (bool), 'code' (str), and
    'errors' (list of str).
    """
    RegisteredSubject = _get_registered_subject_model()
    errors: list[str] = []
    try:
        rs = RegisteredSubject.objects.get(
            subject_identifier=subject_identifier,
        )
    except RegisteredSubject.DoesNotExist:
        return {
            "valid": False,
            "code": "subject_not_found",
            "errors": ["Subject identifier not found."],
        }

    if rs.initials and rs.initials.upper() != initials.upper():
        errors.append(
            f"Initials mismatch: expected '{rs.initials}', got '{initials}'."
        )
    if rs.gender and rs.gender.upper() != sex.upper():
        errors.append(
            f"Sex mismatch: expected '{rs.gender}', got '{sex}'."
        )
    if age is not None and rs.dob:
        today = date.today()
        expected_age = (
            today.year
            - rs.dob.year
            - ((today.month, today.day) < (rs.dob.month, rs.dob.day))
        )
        if abs(expected_age - age) > 1:
            errors.append(
                f"Age mismatch: expected ~{expected_age}, got {age}."
            )
    if errors:
        return {"valid": False, "code": "validation_mismatch", "errors": errors}
    return {"valid": True, "code": "ok", "errors": []}


def _validate_file_content(
    uploaded_file, file_type: str
) -> str | None:
    """Basic magic-byte validation. Returns error message or None."""
    head = uploaded_file.read(8)
    uploaded_file.seek(0)
    if not head:
        return "Uploaded file is empty."
    if file_type == "report":
        if not head.startswith(_PDF_MAGIC):
            return "Report file does not appear to be a valid PDF."
    else:
        # Accept JPEG and PNG for eye images
        if not (head.startswith(_JPEG_MAGIC) or head.startswith(b"\x89PNG")):
            return (
                "Image file does not appear to be a valid JPEG or PNG."
            )
    return None


def _compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file on disk."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_response_data(retinal_image: RetinalImage) -> dict:
    """Build the standard response payload for a RetinalImage."""
    return {
        "id": str(retinal_image.pk),
        "session_id": retinal_image.session_id,
        "file_type": retinal_image.file_type,
        "original_filename": retinal_image.original_filename,
        "stored_filename": retinal_image.stored_filename,
    }


def _find_session(
    subject_identifier: str,
    session_id: int | None = None,
) -> RetinopathySession | None:
    """Find an active session by subject_identifier.

    If session_id is provided, look up that specific session (no expiry
    check — the caller explicitly chose it). Otherwise find the most
    recent non-expired session.
    """
    if session_id is not None:
        return (
            RetinopathySession.objects.filter(
                pk=session_id,
                subject_identifier=subject_identifier,
            )
            .first()
        )
    expire_minutes = _get_session_expire_minutes()
    cutoff = timezone.now() - timedelta(minutes=expire_minutes)
    return (
        RetinopathySession.objects.filter(
            subject_identifier=subject_identifier,
            created_datetime__gte=cutoff,
        )
        .order_by("-created_datetime")
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

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class ResolveSubjectView(APIView):
    """Resolve and validate a subject identifier from the camera.

    POST /api/retinopathy/resolve/

    If an incomplete session already exists for this subject (created
    within the last 24 hours), it is reactivated instead of creating a
    new one. This handles reconnection after an outage.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request: Request) -> Response:
        serializer = ResolveSubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subject_identifier = data["subject_identifier"]
        device_id = data.get("device_id", "")

        result = _validate_subject(
            subject_identifier=subject_identifier,
            initials=data["initials"],
            sex=data["sex"],
            age=data.get("age"),
        )
        if not result["valid"]:
            logger.warning(
                "Resolve failed for %s (device=%s): %s",
                subject_identifier,
                device_id,
                "; ".join(result["errors"]),
            )
            return Response(
                {"code": result["code"], "errors": result["errors"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- Try to reactivate an incomplete session ---
        reactivation_cutoff = timezone.now() - timedelta(
            hours=_get_session_reactivation_hours()
        )
        existing_session = (
            RetinopathySession.objects.filter(
                subject_identifier=subject_identifier,
                created_datetime__gte=reactivation_cutoff,
            )
            .order_by("-created_datetime")
            .first()
        )
        if existing_session:
            uploaded = set(
                existing_session.files.values_list("file_type", flat=True)
            )
            if uploaded != {"left", "right", "report"}:
                # Incomplete — reactivate it
                logger.info(
                    "Reactivating session %s for %s (device=%s, uploaded=%s)",
                    existing_session.pk,
                    subject_identifier,
                    device_id,
                    sorted(uploaded),
                )
                return Response(
                    {
                        "subject_identifier": existing_session.subject_identifier,
                        "session_id": existing_session.pk,
                        "reactivated": True,
                    },
                    status=status.HTTP_200_OK,
                )

        # --- Create new session ---
        session = RetinopathySession.objects.create(
            subject_identifier=subject_identifier,
            initials=data["initials"],
            sex=data["sex"],
            age=data.get("age"),
            device_id=device_id,
            site_id=data.get("site_id", ""),
        )

        logger.info(
            "Session %s created for %s (device=%s)",
            session.pk,
            subject_identifier,
            device_id,
        )

        return Response(
            {
                "subject_identifier": session.subject_identifier,
                "session_id": session.pk,
                "reactivated": False,
            },
            status=status.HTTP_201_CREATED,
        )


class SessionStatusView(APIView):
    """Return the current session status for a subject.

    GET /api/retinopathy/<subject_identifier>/status/
    Returns the most recent session and which file types have been received.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(
        self,
        request: Request,
        subject_identifier: str,
    ) -> Response:
        session = (
            RetinopathySession.objects.filter(
                subject_identifier=subject_identifier,
            )
            .order_by("-created_datetime")
            .first()
        )
        if not session:
            return Response(
                {
                    "code": "no_session",
                    "error": "No session found for this subject.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        uploaded = list(
            session.files.values_list("file_type", flat=True)
        )
        complete = set(uploaded) == {"left", "right", "report"}

        return Response(
            {
                "session_id": session.pk,
                "subject_identifier": session.subject_identifier,
                "created_datetime": session.created_datetime.isoformat(),
                "uploaded": sorted(uploaded),
                "missing": sorted({"left", "right", "report"} - set(uploaded)),
                "complete": complete,
            },
            status=status.HTTP_200_OK,
        )


class FileUploadView(APIView):
    """Receive a file (left eye, right eye, or report) from the camera.

    POST /api/retinopathy/<subject_identifier>/left/
    POST /api/retinopathy/<subject_identifier>/right/
    POST /api/retinopathy/<subject_identifier>/report/

    Query params:
        session_id (optional): Target a specific session instead of the
            most recent one. Useful after reconnection.

    Body: multipart/form-data with 'file', 'capture_datetime', and
    optional 'checksum' (SHA-256 hex digest) fields.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(
        self,
        request: Request,
        subject_identifier: str,
        file_type: str,
    ) -> Response:
        if file_type not in ("left", "right", "report"):
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

        # --- Find session (by explicit session_id or most recent) ---
        raw_session_id = request.query_params.get("session_id")
        session_id = int(raw_session_id) if raw_session_id else None

        session = _find_session(subject_identifier, session_id=session_id)
        if not session:
            expire_minutes = _get_session_expire_minutes()
            error_msg = "No active session found. Call resolve first."
            if session_id:
                error_msg = (
                    f"Session {session_id} not found for "
                    f"subject {subject_identifier}."
                )
            else:
                error_msg += (
                    f" Sessions expire after {expire_minutes} minutes."
                )
            return Response(
                {"code": "no_session", "error": error_msg},
                status=status.HTTP_404_NOT_FOUND,
            )

        # --- Idempotent duplicate check ---
        existing = RetinalImage.objects.filter(
            session=session, file_type=file_type
        ).first()
        if existing:
            logger.info(
                "Duplicate upload for %s/%s session=%s — returning existing",
                subject_identifier,
                file_type,
                session.pk,
            )
            return Response(
                _image_response_data(existing),
                status=status.HTTP_200_OK,
            )

        # --- Save file atomically ---
        ext = Path(uploaded_file.name).suffix.lower() or (
            ".pdf" if file_type == "report" else ".jpg"
        )
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        dest = _get_storage_dir() / stored_filename

        dest.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=str(dest.parent), suffix=f".tmp{ext}"
        )
        try:
            with os.fdopen(fd, "wb") as out:
                for chunk in uploaded_file.chunks():
                    out.write(chunk)
            os.rename(tmp_path, str(dest))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # --- Checksum verification ---
        if checksum:
            actual_hash = _compute_sha256(str(dest))
            if actual_hash != checksum.lower():
                # Delete the corrupt file
                try:
                    os.unlink(str(dest))
                except OSError:
                    pass
                logger.warning(
                    "Checksum mismatch for %s/%s session=%s: "
                    "expected %s, got %s",
                    subject_identifier,
                    file_type,
                    session.pk,
                    checksum.lower(),
                    actual_hash,
                )
                return Response(
                    {
                        "code": "checksum_mismatch",
                        "error": (
                            "File integrity check failed. "
                            f"Expected SHA-256 {checksum}, "
                            f"got {actual_hash}."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        retinal_image = RetinalImage.objects.create(
            session=session,
            file_type=file_type,
            original_filename=uploaded_file.name,
            stored_filename=stored_filename,
            content_type=uploaded_file.content_type or "",
            file_size=uploaded_file.size,
            capture_datetime=capture_datetime,
        )

        logger.info(
            "Received %s for %s session=%s (%s bytes, stored=%s)",
            file_type,
            subject_identifier,
            session.pk,
            uploaded_file.size,
            stored_filename,
        )

        return Response(
            _image_response_data(retinal_image),
            status=status.HTTP_201_CREATED,
        )
