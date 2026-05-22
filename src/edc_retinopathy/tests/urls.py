from django.urls import include, path

urlpatterns = [
    path("api/", include("edc_retinopathy.api.urls")),
]
