=======================
API Developer Reference
=======================

This document describes the REST API exposed by ``edc-retinopathy`` for
integrating a fundus camera with the EDC system.

Overview
========

The camera follows this protocol for each patient encounter:

1. **Ping** the server to verify connectivity and authentication.
2. **Resolve** the subject identifier (confirms a CameraSession exists).
3. **Upload** eye images, DICOM files, and reports.
4. **Check status** to verify all expected files were received.

All endpoints require token authentication and return JSON responses.
Error responses include a machine-readable ``code`` field.

Authentication
==============

Every request must include an ``Authorization`` header with a valid DRF
token:

.. code-block:: text

   Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b

Tokens are created via Django admin under **Auth Token > Tokens**, or
programmatically:

.. code-block:: python

   from rest_framework.authtoken.models import Token
   token = Token.objects.create(user=camera_user)

An unauthenticated request returns ``401 Unauthorized``.

Base URL
========

All endpoints are prefixed with ``/api/retinopathy/``.  Example::

   https://edc.example.com/api/retinopathy/


Endpoints
=========

Health Check (Ping)
-------------------

Verify that the server is reachable and authentication is working.

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``GET /api/retinopathy/ping/``
   * - **Auth**
     - Token (required)

Success response (200)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "status": "ok"
   }


Resolve Subject
---------------

Confirms that a **CameraSession** exists on the server for the given
subject.  The CameraSession must be created by a clinician in the EDC
before the camera exam.

The server walks sessions newest-first and skips any that are
contraindicated or already complete.  If an eligible session is found,
its ID is returned.

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/resolve/``
   * - **Content-Type**
     - ``application/json``
   * - **Auth**
     - Token (required)

Request body
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 10 50

   * - Field
     - Type
     - Required
     - Description
   * - ``subject_identifier``
     - string
     - Yes
     - The subject's unique identifier in the EDC.
   * - ``device_id``
     - string
     - No
     - Identifier for the camera device.  Set on the session if not
       already present.

Success response (200)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "subject_identifier": "105-10-0001-2",
     "camera_session_id": "f8e7d6c5-b4a3-2190-fedc-ba9876543210",
     "uploaded": ["left", "right"]
   }

The ``uploaded`` list shows which file types have already been received
for this session.  Useful for resuming after a disconnect.

Error responses
^^^^^^^^^^^^^^^

No session exists (404):

.. code-block:: json

   {
     "code": "no_session",
     "error": "No camera session found for this subject. Create one in the EDC before conducting the exam."
   }

All sessions complete or contraindicated (400):

.. code-block:: json

   {
     "code": "no_eligible_session",
     "error": "All sessions for this subject are complete or contraindicated. Create a new camera session in the EDC to upload again."
   }


Session Status
--------------

Check which files have been uploaded for the most recent session.

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``GET /api/retinopathy/<subject_identifier>/status/``
   * - **Auth**
     - Token (required)

Success response (200)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "camera_session_id": "f8e7d6c5-b4a3-2190-fedc-ba9876543210",
     "subject_identifier": "105-10-0001-2",
     "report_datetime": "2026-05-21T10:15:30.123456+00:00",
     "uploaded": ["left", "right"],
     "missing": ["report"],
     "complete": false
   }

Error response (404)
^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "code": "no_session",
     "error": "No session found for this subject."
   }


Upload File
-----------

Upload a single file (eye image, DICOM, or report) for a subject.

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/<subject_identifier>/<file_type>/``
   * - **Content-Type**
     - ``multipart/form-data``
   * - **Auth**
     - Token (required)

Valid ``file_type`` values:

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - file_type
     - Accepted formats
     - Description
   * - ``left``
     - JPEG, PNG
     - Left eye image.
   * - ``right``
     - JPEG, PNG
     - Right eye image.
   * - ``left_dicom``
     - DICOM
     - Left eye DICOM file.
   * - ``right_dicom``
     - DICOM
     - Right eye DICOM file.
   * - ``left_report``
     - PDF, HTML
     - Left eye report (per-eye mode).
   * - ``right_report``
     - PDF, HTML
     - Right eye report (per-eye mode).
   * - ``report``
     - PDF, HTML
     - Combined report (both eyes).

**Multiple files per type are accepted.**  For example, the camera may
produce several JPEG images for the same eye.  Each upload creates a new
``SessionFile`` record.

Request body
^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 25 15 10 50

   * - Field
     - Type
     - Required
     - Description
   * - ``file``
     - file
     - Yes
     - The image, DICOM, or report file.
   * - ``capture_datetime``
     - ISO 8601
     - Yes
     - Timestamp when the file was captured by the camera.
   * - ``checksum``
     - string
     - No
     - SHA-256 hex digest.  When provided, the server verifies file
       integrity after writing to disk.

Query parameters
^^^^^^^^^^^^^^^^

``camera_session_id`` (optional)
    Target a specific session instead of the most recent one.  Useful
    after reconnection.  Bypasses the session expiry window.

Success response (201)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "camera_session_id": "f8e7d6c5-b4a3-2190-fedc-ba9876543210",
     "file_type": "left",
     "original_filename": "105-60-00224-7_Retina_OD_20260602_121802.jpg",
     "stored_filename": "f8e7d6c5-b4a3-2190-fedc-ba9876543210/105-60-00224-7_Retina_OD_20260602_121802.jpg",
     "checksum": "92bdbcf8e6dd7955bdf5c8b20985fdac..."
   }

The ``original_filename`` is preserved from the camera.  Files are
stored on disk under ``images/<session_pk>/<original_filename>``.


Content Validation
==================

The server performs basic magic-byte validation on uploaded files:

- **JPEG**: starts with ``FF D8 FF``
- **PNG**: starts with ``89 50 4E 47``
- **PDF**: starts with ``%PDF``
- **HTML**: starts with ``<!doctype``, ``<html>``, ``<head>``, or ``<body>``
- **DICOM**: 128-byte preamble followed by ``DICM`` at offset 128

Invalid content is rejected with ``400`` and ``"code": "invalid_content"``.


Error Codes
===========

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Code
     - HTTP Status
     - Meaning
   * - ``no_session``
     - 404
     - No CameraSession found for this subject, or session expired.
   * - ``no_eligible_session``
     - 400
     - Sessions exist but all are complete or contraindicated.
   * - ``invalid_file_type``
     - 400
     - URL contains an unrecognised file type.
   * - ``invalid_content``
     - 400
     - File content does not match expected format.
   * - ``file_too_large``
     - 400
     - File exceeds ``EDC_RETINOPATHY_MAX_FILE_SIZE_MB``.
   * - ``checksum_mismatch``
     - 400
     - SHA-256 mismatch.  The file was deleted; retry the upload.
   * - ``storage_error``
     - 500
     - File could not be written to disk.  Retry.


File Storage
============

Uploaded files are stored under ``EDC_RETINOPATHY_STORAGE_DIR``:

.. code-block:: text

   /var/edc/retinopathy/
     images/
       f8e7d6c5-b4a3-2190-fedc-ba9876543210/
         105-60-00224-7_Retina_OD_20260602_121802.jpg
         105-60-00224-7_Retina_OS_20260602_121803.jpg
         105-60-00224-7_Retina_OD_20260602_121802.dcm
         105-60-00224-7_Retina_OS_20260602_121803.dcm
         105-60-00224-7_Report_20260602.html
       a1b2c3d4-e5f6-7890-abcd-ef1234567890/
         ...

Each session gets its own subdirectory (named by session PK).  Original
filenames from the camera are preserved.  Files are written atomically
via a temporary file and rename.

The ``images/`` subdirectory must exist before use.  A Django system
check will report an error if it is missing.


Data Model
==========

CameraSession
-------------

Created by the clinician in the EDC before the exam.  Links to
``RegisteredSubject`` and stores screening fields.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - UUIDField
     - Primary key.
   * - ``registered_subject``
     - ForeignKey
     - Link to RegisteredSubject (PROTECT).
   * - ``subject_identifier``
     - CharField
     - Auto-populated from RegisteredSubject on save.
   * - ``report_datetime``
     - DateTimeField
     - When the session was created.
   * - ``report_type``
     - CharField
     - ``combined`` or ``per_eye``.
   * - ``device_id``
     - CharField
     - Camera device identifier (set by resolve).
   * - ``visual_impairment``, ``retinal_conditions``, ``ocular_interventions``, ``photosensitive``, ``pregnant``
     - CharField
     - Contra-indication screening fields (Yes/No/NA).

Properties:

- ``expected_file_types`` -- the set of file types required for
  completeness (depends on ``report_type``).
- ``is_complete`` -- True when all expected file types have been
  uploaded.
- ``contraindicated`` -- True if any screening field is Yes.

SessionFile
-----------

One record per uploaded file, linked to a CameraSession.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - UUIDField
     - Primary key.
   * - ``camera_session``
     - ForeignKey
     - Link to CameraSession (PROTECT).
   * - ``file_type``
     - CharField
     - One of: ``left``, ``right``, ``left_dicom``, ``right_dicom``,
       ``left_report``, ``right_report``, ``report``.
   * - ``original_filename``
     - CharField
     - Filename as sent by the camera.
   * - ``stored_filename``
     - CharField
     - Path on disk relative to ``images/`` (unique).
   * - ``file_content_type``
     - CharField
     - MIME type.
   * - ``file_size``
     - PositiveIntegerField
     - Size in bytes.
   * - ``checksum``
     - CharField
     - SHA-256 hex digest.
   * - ``capture_datetime``
     - DateTimeField
     - Capture timestamp from the camera.
   * - ``received_datetime``
     - DateTimeField
     - Server-side upload timestamp (auto).

**Constraints:** Unique on ``(camera_session, original_filename)`` --
prevents duplicate uploads of the same file within a session.  Multiple
files with the same ``file_type`` are allowed.


Django Configuration
====================

Add ``edc_retinopathy`` to ``INSTALLED_APPS``:

.. code-block:: python

   INSTALLED_APPS = [
       # ...
       "rest_framework",
       "rest_framework.authtoken",
       "edc_retinopathy",
   ]

Include the API URLs:

.. code-block:: python

   # urls.py
   from django.urls import include, path

   urlpatterns = [
       # ...
       path("api/", include("edc_retinopathy.api.urls")),
   ]

Required settings:

.. code-block:: python

   # Path to file storage (must contain an images/ subdirectory)
   EDC_RETINOPATHY_STORAGE_DIR = "/var/edc/retinopathy"

Optional settings:

.. code-block:: python

   # Maximum upload file size in MB (default: 10)
   EDC_RETINOPATHY_MAX_FILE_SIZE_MB = 10

   # Session expiry in minutes (default: 120)
   EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES = 120


Example: Full Workflow
======================

Using ``curl``:

.. code-block:: bash

   TOKEN="your-api-token"
   BASE="https://edc.example.com/api/retinopathy"

   # Ping
   curl -H "Authorization: Token $TOKEN" $BASE/ping/

   # Resolve
   curl -X POST $BASE/resolve/ \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"subject_identifier": "105-10-0001-2", "device_id": "CAM-001"}'

   # Upload left eye image
   curl -X POST $BASE/105-10-0001-2/left/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@105-10-0001-2_Retina_OS_20260602.jpg" \
     -F "capture_datetime=2026-06-02T12:18:02Z"

   # Upload right eye image
   curl -X POST $BASE/105-10-0001-2/right/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@105-10-0001-2_Retina_OD_20260602.jpg" \
     -F "capture_datetime=2026-06-02T12:18:03Z"

   # Upload DICOM files
   curl -X POST $BASE/105-10-0001-2/left_dicom/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@105-10-0001-2_Retina_OS_20260602.dcm" \
     -F "capture_datetime=2026-06-02T12:18:02Z"

   # Upload report
   curl -X POST $BASE/105-10-0001-2/report/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@105-10-0001-2_Report_20260602.html" \
     -F "capture_datetime=2026-06-02T12:18:05Z"

   # Check status
   curl -H "Authorization: Token $TOKEN" \
     $BASE/105-10-0001-2/status/


Logging
=======

The API logs to the ``edc_retinopathy.api.views`` logger:

- **INFO**: Successful resolves, file uploads (subject, session, file
  type, size).
- **WARNING**: Rejected uploads (oversized, invalid content, checksum
  mismatch), no session found.

.. code-block:: python

   LOGGING = {
       "version": 1,
       "handlers": {
           "file": {
               "class": "logging.FileHandler",
               "filename": "/var/log/edc/retinopathy.log",
           },
       },
       "loggers": {
           "edc_retinopathy.api.views": {
               "handlers": ["file"],
               "level": "INFO",
           },
       },
   }
