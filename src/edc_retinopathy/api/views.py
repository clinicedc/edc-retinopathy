from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import RetinalImage, RetinopathyResult
from .serializers import RetinalImageSerializer, RetinopathyResultSerializer


def _get_images_dir() -> Path:
    base = Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser()
    return base / "images"


class RetinopathyResultView(APIView):
    """Receive analysis results from the retinopathy camera.

    POST /api/retinopathy/results/
    Body: JSON with subject_identifier, image_date, analysis_data, etc.
    Returns: created result with id (needed for subsequent image upload).
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request: Request) -> Response:
        serializer = RetinopathyResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RetinalImageUploadView(APIView):
    """Receive retinal image files from the camera.

    POST /api/retinopathy/images/
    Body: multipart/form-data with result_id, eye, image.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        serializer = RetinalImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = RetinopathyResult.objects.get(
            pk=serializer.validated_data["result_id"]
        )
        image_file = serializer.validated_data["image"]
        eye = serializer.validated_data["eye"]

        # Save file to configured directory
        ext = Path(image_file.name).suffix.lower() or ".jpg"
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        dest = _get_images_dir() / stored_filename

        with dest.open("wb") as out:
            for chunk in image_file.chunks():
                out.write(chunk)

        retinal_image = RetinalImage.objects.create(
            result=result,
            eye=eye,
            original_filename=image_file.name,
            stored_filename=stored_filename,
            content_type=image_file.content_type or "",
            file_size=image_file.size,
        )

        return Response(
            {
                "id": str(retinal_image.pk),
                "result_id": result.pk,
                "eye": eye,
                "original_filename": image_file.name,
                "stored_filename": stored_filename,
            },
            status=status.HTTP_201_CREATED,
        )
