=======================
API Developer Reference
=======================

This document describes the REST API exposed by ``edc-retinopathy`` for
integrating a retinopathy camera with the EDC system.

Overview
========

The camera follows a four-step protocol for each patient encounter:

1. **Ping** the server to verify connectivity and authentication.
2. **Resolve** the subject identifier (validates against the EDC registry).
3. **Upload left eye** image.
4. **Upload right eye** image.
5. **Upload report** PDF.

At any point the camera can **check session status** to see which files
have been received and whether the session is complete.

All endpoints require token authentication and return JSON responses.
Every error response includes a machine-readable ``code`` field for
programmatic handling.

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

All endpoints are prefixed with ``/api/retinopathy/``. The base URL
depends on the server configuration, for example::

   https://edc.example.com/api/retinopathy/

Endpoints
=========

Health Check (Ping)
-------------------

Verify that the server is reachable and authentication is working.
Call this before starting a patient workflow.

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


Step 1: Resolve Subject
-----------------------

Validates the subject identifier against ``RegisteredSubject``. If an
incomplete session already exists for this subject (created within the
last 24 hours), it is **reactivated** instead of creating a new one.
This allows the camera to resume after a disconnect without losing
progress. A new session is created only when no recent incomplete session
exists.

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
   * - ``initials``
     - string
     - Yes
     - Subject initials (validated case-insensitively against the registry).
   * - ``sex``
     - string
     - Yes
     - ``"M"`` or ``"F"`` (case-insensitive; normalised to uppercase).
   * - ``age``
     - integer
     - No
     - Subject age in years. Accepted if within 1 year of the calculated age.
   * - ``device_id``
     - string
     - No
     - Identifier for the camera device.
   * - ``site_id``
     - string
     - No
     - Study site identifier.

Success response (201 Created / 200 Reactivated)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New session:

.. code-block:: json

   {
     "subject_identifier": "105-10-0001-2",
     "camera_session_id": 42,
     "reactivated": false
   }

Reactivated session (incomplete session found within 24 hours):

.. code-block:: json

   {
     "subject_identifier": "105-10-0001-2",
     "camera_session_id": 42,
     "reactivated": true
   }

The ``camera_session_id`` can be used in subsequent uploads via the
``?camera_session_id=`` query parameter to target a specific session. If
omitted, uploads are matched to the most recent active session.

Error response (400)
^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "code": "subject_not_found",
     "errors": [
       "Subject identifier not found."
     ]
   }

Multiple validation errors are returned together:

.. code-block:: json

   {
     "code": "validation_mismatch",
     "errors": [
       "Initials mismatch: expected 'JD', got 'XX'.",
       "Sex mismatch: expected 'M', got 'F'.",
       "Age mismatch: expected ~35, got 99."
     ]
   }

Validation rules
^^^^^^^^^^^^^^^^

- ``subject_identifier`` must exist in ``RegisteredSubject``.
- ``initials`` comparison is case-insensitive. Skipped if the registry
  value is blank.
- ``sex`` must be ``"M"`` or ``"F"`` (case-insensitive). Compared against
  ``RegisteredSubject.gender``. Skipped if the registry value is blank.
- ``age`` is compared against the age calculated from
  ``RegisteredSubject.dob``. A tolerance of 1 year is allowed to handle
  birthday boundaries. Skipped if ``age`` is ``null`` or ``dob`` is not
  recorded.


Session Status
--------------

Check which files have been uploaded for the current session. Useful for
resuming after a crash or network interruption.

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
     "camera_session_id": 42,
     "subject_identifier": "105-10-0001-2",
     "created_datetime": "2026-05-21T10:15:30.123456+00:00",
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


Step 2: Upload Left Eye Image
------------------------------

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/<subject_identifier>/left/``
   * - **Query params**
     - ``?camera_session_id=42`` (optional) — target a specific session instead
       of the most recent one. Useful after reconnection.
   * - **Content-Type**
     - ``multipart/form-data``
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
   * - ``file``
     - file
     - Yes
     - The retinal image file (JPEG or PNG).
   * - ``capture_datetime``
     - ISO 8601
     - Yes
     - Timestamp when the image was captured by the camera.
   * - ``checksum``
     - string
     - No
     - SHA-256 hex digest of the file. When provided, the server verifies
       the file integrity after writing to disk. If the hash does not
       match, the file is deleted and ``400`` is returned with code
       ``checksum_mismatch``.

Success response (201)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "camera_session_id": "f8e7d6c5-b4a3-2190-fedc-ba9876543210",
     "file_type": "left",
     "original_filename": "left_eye.jpg",
     "stored_filename": "8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c.jpg",
     "checksum": "92bdbcf8e6dd7955bdf5c8b20985fdac2192791db98ac2ac7c403efb821aeae0"
   }

The ``checksum`` field is always returned and contains the SHA-256 hex
digest of the file as stored on the server.

Checksum verification
^^^^^^^^^^^^^^^^^^^^^

The camera may optionally include a ``checksum`` field (SHA-256 hex digest)
in the upload request. When provided:

- **Match:** The server confirms the stored file is identical to what was
  sent. The upload succeeds with ``201 Created`` and the response includes
  the same checksum.
- **Mismatch:** The stored file is corrupt or was altered in transit. The
  server deletes the file and returns ``400 Bad Request`` with
  ``"code": "checksum_mismatch"``. The camera should retry the upload.

Even when the camera does **not** send a checksum, the response always
includes one. The camera can compare this against its own locally computed
SHA-256 to verify end-to-end integrity after the fact.

Re-upload behaviour
^^^^^^^^^^^^^^^^^^^

If the same file type has already been uploaded for the current session,
re-uploading **replaces** the existing file. The old file is deleted from
disk, the old record is removed, and the new file is saved. The server
returns ``201 Created`` with the new record.

This allows the camera to correct a capture (e.g. with a different
``capture_datetime``) by simply re-sending — the latest upload always wins.
Only one file per type per session is stored at any time.


Step 3: Upload Right Eye Image
-------------------------------

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/<subject_identifier>/right/``
   * - **Content-Type**
     - ``multipart/form-data``
   * - **Auth**
     - Token (required)

Request and response format is identical to Step 2, with
``"file_type": "right"``.


Step 4: Upload Report
---------------------

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/<subject_identifier>/report/``
   * - **Content-Type**
     - ``multipart/form-data``
   * - **Auth**
     - Token (required)

Request and response format is identical to Step 2, with
``"file_type": "report"``. The file must be a PDF.


Error Codes
===========

Every error response includes a ``code`` field for programmatic handling.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Code
     - HTTP Status
     - Meaning
   * - ``subject_not_found``
     - 400
     - Subject identifier does not exist in the registry.
   * - ``validation_mismatch``
     - 400
     - One or more demographics (initials, sex, age) do not match.
   * - ``invalid_file_type``
     - 400
     - URL contains an unrecognised file type (not left/right/report).
   * - ``invalid_content``
     - 400
     - File content does not match expected format (JPEG/PNG for images,
       PDF for reports).
   * - ``file_too_large``
     - 400
     - File exceeds the configured maximum size.
   * - ``checksum_mismatch``
     - 400
     - SHA-256 of the stored file does not match the provided checksum.
       The file was deleted; retry the upload.
   * - ``no_session``
     - 404
     - No active session found. Either resolve was not called, or the
       session has expired.


Error Responses
===============

All endpoints share these common HTTP error statuses:

.. list-table::
   :header-rows: 1
   :widths: 15 30 55

   * - Status
     - Meaning
     - When
   * - ``400``
     - Bad Request
     - Missing required fields, validation mismatch, invalid file type,
       invalid content, or file too large.
   * - ``401``
     - Unauthorized
     - Missing or invalid authentication token.
   * - ``404``
     - Not Found
     - Upload attempted with no active session (not resolved, or session
       expired).


File Storage
============

Uploaded files are stored in the directory configured by
``EDC_RETINOPATHY_STORAGE_DIR`` in Django settings:

.. code-block:: python

   # settings.py
   EDC_RETINOPATHY_STORAGE_DIR = "/var/edc/retinopathy"

Files are saved under the ``images/`` subdirectory with UUID-based
filenames to avoid collisions and prevent exposure of patient information
in filenames. The original filename is preserved in the database.

Files are written atomically (via a temporary file and rename) to prevent
corrupt partial files if the server crashes during upload.

Directory structure::

   /var/edc/retinopathy/
     images/
       8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c.jpg
       a1b2c3d4e5f6789012345678abcdef01.jpg
       f0e1d2c3b4a596870123456789abcdef.pdf

The ``images/`` subdirectory must be created before use. A Django system
check will report an error if it is missing.


Data Model
==========

RetinopathySession
------------------

Created on each ``resolve`` call. Groups all files from one camera
encounter.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - BigAutoField
     - Primary key.
   * - ``subject_identifier``
     - CharField
     - The resolved subject identifier.
   * - ``initials``
     - CharField
     - Initials as sent by the camera.
   * - ``sex``
     - CharField
     - Sex as sent by the camera.
   * - ``age``
     - IntegerField
     - Age in years as sent by the camera.
   * - ``device_id``
     - CharField
     - Camera device identifier.
   * - ``site_id``
     - CharField
     - Study site identifier.
   * - ``created_datetime``
     - DateTimeField
     - Timestamp of session creation (auto).

SessionFile
------------

One record per uploaded file, linked to a session.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``id``
     - UUIDField
     - Primary key (auto-generated UUID).
   * - ``session``
     - ForeignKey
     - Link to ``RetinopathySession`` (PROTECT on delete).
   * - ``file_type``
     - CharField
     - One of ``left``, ``right``, or ``report``.
   * - ``original_filename``
     - CharField
     - Filename as sent by the camera.
   * - ``stored_filename``
     - CharField
     - UUID-based filename on disk (unique).
   * - ``content_type``
     - CharField
     - MIME type (e.g. ``image/jpeg``, ``application/pdf``).
   * - ``file_size``
     - PositiveIntegerField
     - File size in bytes.
   * - ``capture_datetime``
     - DateTimeField
     - Capture timestamp as reported by the camera (required).
   * - ``received_datetime``
     - DateTimeField
     - Timestamp of upload (auto).

**Constraints:** A unique constraint on ``(session, file_type)`` ensures
at most one file per type per session. Re-uploading replaces the existing
file (the old record is deleted before the new one is created).


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

   # Path to file storage directory (must exist, with images/ subdirectory)
   EDC_RETINOPATHY_STORAGE_DIR = "/var/edc/retinopathy"

   # RegisteredSubject model (default shown)
   EDC_REGISTRATION_REGISTERED_SUBJECT_MODEL = "edc_registration.registeredsubject"

Optional settings:

.. code-block:: python

   # Maximum upload file size in MB (default: 10)
   EDC_RETINOPATHY_MAX_FILE_SIZE_MB = 10

   # Session expiry in minutes (default: 120).
   # Uploads to sessions older than this are rejected (unless camera_session_id
   # is specified explicitly in the query string).
   EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES = 120

Logging
=======

The API logs all requests to the ``edc_retinopathy.api.views`` logger:

- **INFO**: Successful resolves and file uploads (subject, session, device,
  file type, size).
- **WARNING**: Failed resolves (validation mismatches, unknown subjects),
  rejected uploads (oversized files, invalid content).

Configure in Django ``LOGGING``:

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


Example: Full Workflow
======================

Using ``curl`` to demonstrate the complete protocol:

.. code-block:: bash

   TOKEN="9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"  # ggignore
   BASE="https://edc.example.com/api/retinopathy"

   # Step 0: Verify connectivity
   curl -H "Authorization: Token $TOKEN" $BASE/ping/

   # Step 1: Resolve subject
   curl -X POST $BASE/resolve/ \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "subject_identifier": "105-10-0001-2",
       "initials": "JD",
       "sex": "M",
       "age": 35,
       "device_id": "CAM-001",
       "site_id": "SITE-A"
     }'

   # Step 2: Upload left eye image (with checksum for integrity)
   CHECKSUM=$(sha256sum /path/to/left_eye.jpg | cut -d' ' -f1)
   curl -X POST $BASE/105-10-0001-2/left/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@/path/to/left_eye.jpg" \
     -F "capture_datetime=2026-05-21T10:30:00Z" \
     -F "checksum=$CHECKSUM"

   # Step 3: Upload right eye image (targeting a specific session)
   curl -X POST "$BASE/105-10-0001-2/right/?camera_session_id=42" \
     -H "Authorization: Token $TOKEN" \
     -F "file=@/path/to/right_eye.jpg" \
     -F "capture_datetime=2026-05-21T10:31:00Z"

   # Step 4: Upload report PDF
   curl -X POST $BASE/105-10-0001-2/report/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@/path/to/report.pdf" \
     -F "capture_datetime=2026-05-21T10:32:00Z"

   # Check session status at any point
   curl -H "Authorization: Token $TOKEN" \
     $BASE/105-10-0001-2/status/


Example: Recovery After Network Failure
=======================================

If the camera loses connectivity after uploading the left eye, it can
recover by checking the session status:

.. code-block:: bash

   # Camera reconnects and checks what was received
   curl -H "Authorization: Token $TOKEN" \
     $BASE/105-10-0001-2/status/
   # Response: {"uploaded": ["left"], "missing": ["report", "right"], ...}

   # Camera skips left (already done) and continues with right
   curl -X POST $BASE/105-10-0001-2/right/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@/path/to/right_eye.jpg"

   # Or if the camera retries left anyway, it gets 200 (not an error)
   curl -X POST $BASE/105-10-0001-2/left/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@/path/to/left_eye.jpg"
   # Returns 200 with the existing record — safe to retry
