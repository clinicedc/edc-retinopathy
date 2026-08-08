"""Views for ophthalmologist DICOM review workflow."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.views.generic import DetailView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin

from ..models import EyeExamRegister


class ReviewDetailView(EdcViewMixin, NavbarViewMixin, DetailView):
    """Show DICOM previews for a single session."""

    template_name = "edc_retinopathy/review_detail.html"
    context_object_name = "eye_exam_register"
    navbar_selected_item = "edc_lab_results"

    def get_object(self, queryset=None):
        return get_object_or_404(EyeExamRegister, pk=self.kwargs["session_pk"])

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
