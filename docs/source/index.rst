edc-retinopathy
===============

``edc-retinopathy`` adds a diabetic retinopathy screening form and REST
API for integrating a fundus camera with a clinicedc project.

A clinician creates a **CameraSession** in the EDC before the exam.  The
camera software (``fundus-camera-watchdog``) resolves the subject against
the server, uploads eye images, DICOM files, and reports, then checks
session status.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api
