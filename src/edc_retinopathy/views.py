from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from .models import SessionFile


def _get_storage_dir() -> Path:
    base = Path(settings.EDC_RETINOPATHY_STORAGE_DIR).expanduser()
    return base / "images"


@login_required
def report_view(request, session_file_id: str) -> HttpResponse:  # noqa: ARG001
    """Serve a stored HTML report for viewing in the browser."""
    session_file = get_object_or_404(SessionFile, pk=session_file_id)
    stored_path = _get_storage_dir() / session_file.stored_filename
    if not stored_path.is_file():
        msg = "Report file not found on disk."
        raise Http404(msg)
    content_type = session_file.file_content_type or "text/html"
    return HttpResponse(
        stored_path.read_bytes(),
        content_type=content_type,
    )
