from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from ..models import SessionFile
from ..utils import get_storage_dir

__all__ = ["stored_image_view"]


@login_required
def stored_image_view(
    request,  # noqa: ARG001
    session_file_id: str,
) -> HttpResponse:
    """Serve a stored image file (JPEG/PNG) directly."""
    session_file = get_object_or_404(SessionFile, pk=session_file_id)
    stored_path = get_storage_dir() / session_file.stored_filename
    if not stored_path.is_file():
        msg = "File not found on disk."
        raise Http404(msg)
    content_type = session_file.file_content_type or "image/jpeg"
    return HttpResponse(stored_path.read_bytes(), content_type=content_type)
