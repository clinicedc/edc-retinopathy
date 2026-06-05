from __future__ import annotations

from django.views.generic import TemplateView
from edc_dashboard.view_mixins import EdcViewMixin
from edc_navbar import NavbarViewMixin


class HomeView(EdcViewMixin, NavbarViewMixin, TemplateView):
    template_name = "edc_retinopathy/home.html"
    navbar_selected_item = "edc_lab_results"
