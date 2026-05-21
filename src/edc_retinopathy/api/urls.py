from django.urls import path

from .views import FileUploadView, PingView, ResolveSubjectView, SessionStatusView

app_name = "edc_retinopathy_api"

urlpatterns = [
    path(
        "retinopathy/ping/",
        PingView.as_view(),
        name="ping",
    ),
    path(
        "retinopathy/resolve/",
        ResolveSubjectView.as_view(),
        name="resolve-subject",
    ),
    path(
        "retinopathy/<str:subject_identifier>/status/",
        SessionStatusView.as_view(),
        name="session-status",
    ),
    path(
        "retinopathy/<str:subject_identifier>/<str:file_type>/",
        FileUploadView.as_view(),
        name="file-upload",
    ),
]
