|pypi| |actions| |codecov| |downloads| |clinicedc|

edc-retinopathy
---------------

Add a diabetic retinopathy screening form and REST API for integrating
with a fundus camera in a clinicedc project.

A clinician creates a **CameraSession** in the EDC before the exam.  The
camera software (``fundus-camera-watchdog``) resolves the subject,
uploads eye images, DICOM files and reports, then checks status.

Requires django>=5.2,<6.1 and djangorestframework>=3.16.0

REST API
~~~~~~~~

All endpoints use ``TokenAuthentication``.

``GET /api/retinopathy/ping/``
    Health check.  Returns ``{"status": "ok"}``.

``POST /api/retinopathy/resolve/``
    Confirm a CameraSession exists for a subject.  Payload::

        {"subject_identifier": "105-10-0001-2"}

    Returns ``200`` with ``camera_session_id`` and ``uploaded`` list, or
    ``404`` if no session exists.

``POST /api/retinopathy/<subject_identifier>/<file_type>/``
    Upload a file.  Multipart form with ``file``, ``capture_datetime``,
    and optional ``checksum`` (SHA-256).  Valid file types:

    - ``left``, ``right`` -- eye images (JPEG/PNG)
    - ``left_dicom``, ``right_dicom`` -- DICOM files
    - ``left_report``, ``right_report``, ``report`` -- reports (PDF/HTML)

    Multiple files per type are accepted.  Files are stored with their
    original filenames under ``<storage_dir>/images/<session_pk>/``.

``GET /api/retinopathy/<subject_identifier>/status/``
    Session status: uploaded types, missing types, and whether the
    session is complete.

Models
~~~~~~

``CameraSession``
    Created by the clinician in the EDC.  Links to ``RegisteredSubject``
    and stores contra-indication screening fields, report type
    (combined / per-eye), and device ID.

``SessionFile``
    One record per uploaded file.  Tracks file type, original filename,
    stored path, content type, size, SHA-256 checksum, and capture
    timestamp.

Settings
~~~~~~~~

``EDC_RETINOPATHY_STORAGE_DIR``
    Base path for file storage.  Must contain an ``images/`` subdirectory.

``EDC_RETINOPATHY_MAX_FILE_SIZE_MB``
    Maximum upload size in MB (default: 10).

``EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES``
    Session expiry window in minutes (default: 120).

See also https://edc-retinopathy.readthedocs.io/en/latest/

.. |pypi| image:: https://img.shields.io/pypi/v/edc-retinopathy.svg
    :target: https://pypi.python.org/pypi/edc-retinopathy

.. |actions| image:: https://github.com/clinicedc/edc-retinopathy/actions/workflows/build.yml/badge.svg
  :target: https://github.com/clinicedc/edc-retinopathy/actions/workflows/build.yml

.. |codecov| image:: https://codecov.io/gh/clinicedc/edc-retinopathy/branch/develop/graph/badge.svg
  :target: https://codecov.io/gh/clinicedc/edc-retinopathy

.. |downloads| image:: https://pepy.tech/badge/edc-retinopathy
   :target: https://pepy.tech/project/edc-retinopathy

.. |clinicedc| image:: https://img.shields.io/badge/framework-Clinic_EDC-green
   :alt:Made with clinicedc
   :target: https://github.com/clinicedc
