"""Views for ophthalmologist DICOM review workflow."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin

from ..models import CameraSession, DmRetinopathyScreening, SessionFile


def _get_storage_dir() -> Path:
    return Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser() / "images"


class ReviewQueueView(EdcViewMixin, NavbarViewMixin, ListView):
    """List sessions that have DICOM uploads but no screening yet."""

    template_name = "edc_retinopathy/review_queue.html"
    context_object_name = "sessions"
    navbar_selected_item = "edc_lab_results"

    def get_queryset(self):
        has_dicoms = Exists(
            SessionFile.objects.filter(
                camera_session=OuterRef("pk"),
                file_type__in=("left_dicom", "right_dicom"),
            ),
        )
        has_screening = Exists(
            DmRetinopathyScreening.objects.filter(
                camera_session=OuterRef("pk"),
            ),
        )
        return (
            CameraSession.objects.filter(has_dicoms)
            .exclude(has_screening)
            .annotate(
                od_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="right_dicom"),
                ),
                os_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="left_dicom"),
                ),
            )
            .order_by("-report_datetime")
        )


class ReviewedQueueView(EdcViewMixin, NavbarViewMixin, ListView):
    """List sessions that have already been reviewed (screening exists)."""

    template_name = "edc_retinopathy/reviewed_queue.html"
    context_object_name = "sessions"
    navbar_selected_item = "edc_lab_results"
    paginate_by = 50

    def get_queryset(self):
        has_dicoms = Exists(
            SessionFile.objects.filter(
                camera_session=OuterRef("pk"),
                file_type__in=("left_dicom", "right_dicom"),
            ),
        )
        has_screening = Exists(
            DmRetinopathyScreening.objects.filter(
                camera_session=OuterRef("pk"),
            ),
        )
        return (
            CameraSession.objects.filter(has_dicoms)
            .filter(has_screening)
            .annotate(
                od_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="right_dicom"),
                ),
                os_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="left_dicom"),
                ),
            )
            .order_by("-report_datetime")
        )


class ReviewDetailView(EdcViewMixin, NavbarViewMixin, DetailView):
    """Show DICOM previews for a single session."""

    template_name = "edc_retinopathy/review_detail.html"
    context_object_name = "camera_session"
    navbar_selected_item = "edc_lab_results"

    def get_object(self, queryset=None):
        return get_object_or_404(CameraSession, pk=self.kwargs["session_pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object
        dicom_files = session.files.filter(
            file_type__in=("left_dicom", "right_dicom"),
        ).order_by("file_type", "capture_datetime")
        od_files = [f for f in dicom_files if f.file_type == "right_dicom"]
        os_files = [f for f in dicom_files if f.file_type == "left_dicom"]
        image_files = session.files.filter(
            file_type__in=("left", "right"),
        ).order_by("file_type", "capture_datetime")
        od_images = [f for f in image_files if f.file_type == "right"]
        os_images = [f for f in image_files if f.file_type == "left"]
        context.update(
            od_files=od_files,
            os_files=os_files,
            od_images=od_images,
            os_images=os_images,
        )
        return context


@login_required
def preview_image_view(
    request,  # noqa: ARG001
    session_file_id: str,
) -> HttpResponse:
    """Serve a JPEG preview image for a DICOM file."""
    session_file = get_object_or_404(SessionFile, pk=session_file_id)
    if not session_file.preview_filename:
        msg = "No preview available for this file."
        raise Http404(msg)
    preview_path = _get_storage_dir() / session_file.preview_filename
    if not preview_path.is_file():
        msg = "Preview file not found on disk."
        raise Http404(msg)
    return HttpResponse(preview_path.read_bytes(), content_type="image/jpeg")


@login_required
def stored_image_view(
    request,  # noqa: ARG001
    session_file_id: str,
) -> HttpResponse:
    """Serve a stored image file (JPEG/PNG) directly."""
    session_file = get_object_or_404(SessionFile, pk=session_file_id)
    stored_path = _get_storage_dir() / session_file.stored_filename
    if not stored_path.is_file():
        msg = "File not found on disk."
        raise Http404(msg)
    content_type = session_file.file_content_type or "image/jpeg"
    return HttpResponse(stored_path.read_bytes(), content_type=content_type)
