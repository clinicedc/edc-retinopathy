from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import RetinalImage, RetinopathySession
from .serializers import ResolveSubjectSerializer, FileUploadSerializer


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
    age: int,
) -> dict:
    """Validate subject against RegisteredSubject.

    Returns a dict with 'valid' (bool) and 'errors' (list of str).
    """
    RegisteredSubject = _get_registered_subject_model()
    errors = []
    try:
        rs = RegisteredSubject.objects.get(
            subject_identifier=subject_identifier,
        )
    except RegisteredSubject.DoesNotExist:
        return {"valid": False, "errors": ["Subject identifier not found."]}

    if initials and rs.initials and rs.initials.upper() != initials.upper():
        errors.append(
            f"Initials mismatch: expected '{rs.initials}', got '{initials}'."
        )
    if sex and rs.gender and rs.gender.upper() != sex.upper():
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
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": []}


class ResolveSubjectView(APIView):
    """Resolve and validate a subject identifier from the camera.

    POST /api/retinopathy/resolve/
    Body: JSON with subject_identifier, initials, sex, age.
    Returns: confirmed subject_identifier and session_id.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request: Request) -> Response:
        serializer = ResolveSubjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = _validate_subject(
            subject_identifier=data["subject_identifier"],
            initials=data.get("initials", ""),
            sex=data.get("sex", ""),
            age=data.get("age"),
        )
        if not result["valid"]:
            return Response(
                {"errors": result["errors"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = RetinopathySession.objects.create(
            subject_identifier=data["subject_identifier"],
            initials=data.get("initials", ""),
            sex=data.get("sex", ""),
            age=data.get("age"),
            device_id=data.get("device_id", ""),
            site_id=data.get("site_id", ""),
        )

        return Response(
            {
                "subject_identifier": session.subject_identifier,
                "session_id": session.pk,
            },
            status=status.HTTP_201_CREATED,
        )


class FileUploadView(APIView):
    """Receive a file (left eye, right eye, or report) from the camera.

    POST /api/retinopathy/<subject_identifier>/left/
    POST /api/retinopathy/<subject_identifier>/right/
    POST /api/retinopathy/<subject_identifier>/report/
    Body: multipart/form-data with 'file' field.
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
                {"error": f"Invalid file type: '{file_type}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Find the most recent session for this subject
        session = (
            RetinopathySession.objects.filter(
                subject_identifier=subject_identifier,
            )
            .order_by("-created_datetime")
            .first()
        )
        if not session:
            return Response(
                {"error": "No session found. Call resolve first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check for duplicate file_type on this session
        if RetinalImage.objects.filter(
            session=session, file_type=file_type
        ).exists():
            return Response(
                {
                    "error": (
                        f"A '{file_type}' file has already been uploaded "
                        f"for session {session.pk}."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        uploaded_file = serializer.validated_data["file"]

        # Save file to storage
        ext = Path(uploaded_file.name).suffix.lower() or (
            ".pdf" if file_type == "report" else ".jpg"
        )
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        dest = _get_storage_dir() / stored_filename

        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as out:
            for chunk in uploaded_file.chunks():
                out.write(chunk)

        retinal_image = RetinalImage.objects.create(
            session=session,
            file_type=file_type,
            original_filename=uploaded_file.name,
            stored_filename=stored_filename,
            content_type=uploaded_file.content_type or "",
            file_size=uploaded_file.size,
        )

        return Response(
            {
                "id": str(retinal_image.pk),
                "session_id": session.pk,
                "file_type": file_type,
                "original_filename": uploaded_file.name,
                "stored_filename": stored_filename,
            },
            status=status.HTTP_201_CREATED,
        )
