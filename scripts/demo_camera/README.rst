Demo camera script
==================

``demo_camera.py`` simulates the retinopathy camera's four-step workflow
against a live server. Use it to verify end-to-end connectivity after
installing ``edc-retinopathy`` in a study EDC.

Prerequisites
-------------

1. Install ``edc-retinopathy`` in your EDC project (e.g. ``meta-edc``).

2. Add to ``INSTALLED_APPS``::

       INSTALLED_APPS = [
           ...
           "rest_framework",
           "rest_framework.authtoken",
           "edc_retinopathy.apps.AppConfig",
           ...
       ]

   Then run migrations to create the token table::

       python manage.py migrate authtoken

3. Wire the API URLs (in your project's ``urls.py``)::

       from edc_retinopathy.api.urls import urlpatterns as retinopathy_urls

       urlpatterns = [
           ...
           path("api/", include(retinopathy_urls)),
           ...
       ]

4. Add settings::

       EDC_RETINOPATHY_STORAGE_DIR = "/path/to/retinal-images"
       EDC_RETINOPATHY_MAX_FILE_SIZE_MB = 10          # default
       EDC_RETINOPATHY_SESSION_EXPIRE_MINUTES = 120   # default

5. Create the storage directory::

       mkdir -p /path/to/retinal-images/images

6. Create an API token (Django shell or admin)::

       from django.contrib.auth.models import User
       from rest_framework.authtoken.models import Token

       user, _ = User.objects.get_or_create(username="camera")
       token, _ = Token.objects.get_or_create(user=user)
       print(token.key)

Usage
-----

Basic (uses dummy files)::

    python demo_camera.py \
        --host http://localhost:8000 \
        --token YOUR_TOKEN \
        --subject 105-10-0001-2 \
        --initials JD \
        --sex M \
        --age 35

With real image files::

    python demo_camera.py \
        --host http://localhost:8000 \
        --token YOUR_TOKEN \
        --subject 105-10-0001-2 \
        --initials JD \
        --sex M \
        --left-image /path/to/left_eye.jpg \
        --right-image /path/to/right_eye.jpg \
        --report /path/to/report.pdf

With SHA-256 checksum verification::

    python demo_camera.py \
        --host http://localhost:8000 \
        --token YOUR_TOKEN \
        --subject 105-10-0001-2 \
        --initials JD \
        --sex M \
        --checksum

What it does
------------

The script executes the camera's protocol in order:

0. **Ping** — verifies the server is reachable and the token is valid.
1. **Resolve** — looks up the subject and creates (or reactivates) a session.
2. **Upload left eye** — sends a JPEG image with capture datetime.
3. **Upload right eye** — sends a JPEG image with capture datetime.
4. **Upload report** — sends the PDF analysis report.
5. **Status** — confirms the session is complete.

Each step prints its result. The script exits on the first failure
(except upload failures, which are logged and skipped).

Dependencies
------------

The script requires ``requests``::

    pip install requests
