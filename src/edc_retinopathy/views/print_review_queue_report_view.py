from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from ..pdf_reports import ReviewQueueReport


@login_required
def print_review_queue_report_view(request) -> HttpResponse:
    """Serve the DICOM review queue as a downloadable PDF report."""
    response = HttpResponse(content_type="application/pdf")
    filename = f"dicom_review_queue_{timezone.now().strftime('%Y-%m-%d_%H%M')}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    page = dict(
        rightMargin=1 * cm,
        leftMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        pagesize=A4,
    )
    report = ReviewQueueReport(request=request, page=page)
    report.build(response)
    return response
