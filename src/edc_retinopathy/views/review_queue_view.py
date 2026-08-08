from django.contrib.sites.models import Site
from django.db.models import Count, Exists, OuterRef, Q
from django.views.generic import ListView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin
from edc_sites.site import sites

from ..models import DmRetinopathyScreening, EyeExamRegister, SessionFile

__all__ = ["ReviewQueueView", "ReviewedQueueView"]


class ReviewQueueView(EdcViewMixin, NavbarViewMixin, ListView):
    """List sessions not yet reviewed (no screening), whether or not the
    camera has uploaded images yet.
    """

    template_name = "edc_retinopathy/review_queue.html"
    context_object_name = "sessions"
    navbar_selected_item = "edc_lab_results"

    def get_queryset(self):
        has_dicoms = Exists(
            SessionFile.objects.filter(
                eye_exam_register=OuterRef("pk"),
                file_type__in=("left_dicom", "right_dicom"),
            ),
        )
        has_screening = Exists(
            DmRetinopathyScreening.objects.filter(
                eye_exam_register=OuterRef("pk"),
            ),
        )
        return (
            EyeExamRegister.objects.exclude(has_screening)
            .annotate(
                uploaded=has_dicoms,
                od_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="right_dicom"),
                ),
                os_dicom_count=Count(
                    "files",
                    filter=Q(files__file_type="left_dicom"),
                ),
            )
            .order_by("-uploaded", "-report_datetime")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_titles = {site.id: sites.get(site.id).title for site in Site.objects.all()}
        sessions = list(context["sessions"])
        for session in sessions:
            session.site_title = site_titles.get(session.site_id, "")
        context["sessions"] = sessions
        context["object_list"] = sessions
        context["site_choices"] = sorted(
            {session.site_title for session in sessions if session.site_title},
        )
        return context


class ReviewedQueueView(EdcViewMixin, NavbarViewMixin, ListView):
    """List sessions that have already been reviewed (screening exists)."""

    template_name = "edc_retinopathy/reviewed_queue.html"
    context_object_name = "sessions"
    navbar_selected_item = "edc_lab_results"

    def get_queryset(self):
        has_dicoms = Exists(
            SessionFile.objects.filter(
                eye_exam_register=OuterRef("pk"),
                file_type__in=("left_dicom", "right_dicom"),
            ),
        )
        has_screening = Exists(
            DmRetinopathyScreening.objects.filter(
                eye_exam_register=OuterRef("pk"),
            ),
        )
        return (
            EyeExamRegister.objects.filter(has_dicoms)
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
