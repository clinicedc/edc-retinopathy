from django.urls import include, path
from django.views.generic import RedirectView

from .admin_site import edc_retinopathy_admin
from .views import report_view

app_name = "edc_retinopathy"

urlpatterns = [
    path("api/", include("edc_retinopathy.api.urls")),
    path("admin/", edc_retinopathy_admin.urls),
    path(
        "report/<str:session_file_id>/",
        report_view,
        name="report-view",
    ),
    path("", RedirectView.as_view(url=f"/{app_name}/admin/"), name="home_url"),
]
