from django.urls import path

from .views import FileUploadView, ResolveSubjectView

app_name = "edc_retinopathy_api"

urlpatterns = [
    path(
        "retinopathy/resolve/",
        ResolveSubjectView.as_view(),
        name="resolve-subject",
    ),
    path(
        "retinopathy/<str:subject_identifier>/<str:file_type>/",
        FileUploadView.as_view(),
        name="file-upload",
    ),
]
