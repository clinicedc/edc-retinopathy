from django.urls import include, path

app_name = "edc_retinopathy"

urlpatterns = [
    path("api/", include("edc_retinopathy.api.urls")),
]
