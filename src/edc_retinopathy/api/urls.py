from django.urls import path

from .views import RetinalImageUploadView, RetinopathyResultView

app_name = "edc_retinopathy_api"

urlpatterns = [
    path(
        "retinopathy/results/",
        RetinopathyResultView.as_view(),
        name="results",
    ),
    path(
        "retinopathy/images/",
        RetinalImageUploadView.as_view(),
        name="images",
    ),
]
