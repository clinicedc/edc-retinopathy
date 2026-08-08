from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from ..models import SessionFile
from ..utils import get_storage_dir

__all__ = ["preview_image_view"]


@login_required
def preview_image_view(
    request,  # noqa: ARG001
    session_file_id: str,
) -> HttpResponse:
    """Serve a JPEG preview image for a DICOM file."""
    session_file = get_object_or_404(SessionFile, pk=session_file_id)
    if not session_file.preview_filename:
        msg = "No preview available for this file."
        raise Http404(msg)
    preview_path = get_storage_dir() / session_file.preview_filename
    if not preview_path.is_file():
        msg = "Preview file not found on disk."
        raise Http404(msg)
    return HttpResponse(preview_path.read_bytes(), content_type="image/jpeg")
