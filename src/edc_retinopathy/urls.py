from django.urls import include, path

from .admin_site import edc_retinopathy_admin
from .views import (
    HomeView,
    ReviewDetailView,
    ReviewedQueueView,
    ReviewQueueView,
    preview_image_view,
    report_view,
    stored_image_view,
)

app_name = "edc_retinopathy"

urlpatterns = [
    path("api/", include("edc_retinopathy.api.urls")),
    path("admin/", edc_retinopathy_admin.urls),
    path(
        "report/<str:session_file_id>/",
        report_view,
        name="report-view",
    ),
    path(
        "review/",
        ReviewQueueView.as_view(),
        name="review-queue",
    ),
    path(
        "reviewed/",
        ReviewedQueueView.as_view(),
        name="reviewed-queue",
    ),
    path(
        "review/<str:session_pk>/",
        ReviewDetailView.as_view(),
        name="review-detail",
    ),
    path(
        "preview/<str:session_file_id>/",
        preview_image_view,
        name="preview-image",
    ),
    path(
        "image/<str:session_file_id>/",
        stored_image_view,
        name="stored-image",
    ),
    path("", HomeView.as_view(), name="home_url"),
]
