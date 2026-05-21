=======================
API Developer Reference
=======================

This document describes the REST API exposed by ``edc-retinopathy`` for
integrating a retinopathy camera with the EDC system.

Overview
========

The camera follows a four-step protocol for each patient encounter:

1. **Resolve** the subject identifier (validates against the EDC registry).
2. **Upload left eye** image.
3. **Upload right eye** image.
4. **Upload report** PDF.

All endpoints require token authentication and return JSON responses.

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

Step 1: Resolve Subject
-----------------------

Validates the subject identifier against ``RegisteredSubject`` and creates
a new session record that groups all subsequent uploads.

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
     - No
     - Subject initials (validated case-insensitively against the registry).
   * - ``sex``
     - string
     - No
     - Subject sex, e.g. ``"M"`` or ``"F"`` (validated case-insensitively).
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

Success response (201)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "subject_identifier": "105-10-0001-2",
     "session_id": 42
   }

The ``session_id`` is used internally to link uploads. The camera does not
need to track it; subsequent uploads are matched by ``subject_identifier``
to the most recent session.

Error response (400)
^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "errors": [
       "Subject identifier not found."
     ]
   }

Multiple validation errors are returned together:

.. code-block:: json

   {
     "errors": [
       "Initials mismatch: expected 'JD', got 'XX'.",
       "Sex mismatch: expected 'M', got 'F'.",
       "Age mismatch: expected ~35, got 99."
     ]
   }

Validation rules
^^^^^^^^^^^^^^^^

- ``subject_identifier`` must exist in ``RegisteredSubject``.
- ``initials`` comparison is case-insensitive. Skipped if the camera sends
  an empty string or the registry value is blank.
- ``sex`` is compared against ``RegisteredSubject.gender``
  (case-insensitive). Skipped if empty on either side.
- ``age`` is compared against the age calculated from
  ``RegisteredSubject.dob``. A tolerance of 1 year is allowed to handle
  birthday boundaries. Skipped if ``age`` is ``null`` or ``dob`` is not
  recorded.


Step 2: Upload Left Eye Image
------------------------------

.. list-table::
   :widths: 20 80

   * - **URL**
     - ``POST /api/retinopathy/<subject_identifier>/left/``
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
     - The retinal image file (JPEG, PNG, etc.).

Success response (201)
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: json

   {
     "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
     "session_id": 42,
     "file_type": "left",
     "original_filename": "left_eye.jpg",
     "stored_filename": "8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c.jpg"
   }


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
``"file_type": "report"``. The file is expected to be a PDF.


Error Responses
===============

All endpoints share these common error responses:

.. list-table::
   :header-rows: 1
   :widths: 15 30 55

   * - Status
     - Meaning
     - When
   * - ``400``
     - Bad Request
     - Missing required fields, validation mismatch, or invalid file type
       in URL.
   * - ``401``
     - Unauthorized
     - Missing or invalid authentication token.
   * - ``404``
     - Not Found
     - Upload attempted for a subject with no prior ``resolve`` call
       (no session exists).
   * - ``409``
     - Conflict
     - A file of the same type (left, right, or report) has already been
       uploaded for the current session.


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

RetinalImage
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
   * - ``received_datetime``
     - DateTimeField
     - Timestamp of upload (auto).

**Constraints:** A unique constraint on ``(session, file_type)`` prevents
duplicate uploads of the same type within a session.


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


Example: Full Workflow
======================

Using ``curl`` to demonstrate the four-step protocol:

.. code-block:: bash

   # Step 1: Resolve subject
   curl -X POST https://edc.example.com/api/retinopathy/resolve/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     -H "Content-Type: application/json" \
     -d '{
       "subject_identifier": "105-10-0001-2",
       "initials": "JD",
       "sex": "M",
       "age": 35,
       "device_id": "CAM-001",
       "site_id": "SITE-A"
     }'

   # Step 2: Upload left eye image
   curl -X POST https://edc.example.com/api/retinopathy/105-10-0001-2/left/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     -F "file=@/path/to/left_eye.jpg"

   # Step 3: Upload right eye image
   curl -X POST https://edc.example.com/api/retinopathy/105-10-0001-2/right/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     -F "file=@/path/to/right_eye.jpg"

   # Step 4: Upload report PDF
   curl -X POST https://edc.example.com/api/retinopathy/105-10-0001-2/report/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
     -F "file=@/path/to/report.pdf"
