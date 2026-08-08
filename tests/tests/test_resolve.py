"""Tests for the resolve-subject endpoint.

The camera calls resolve to confirm a EyeExamRegister exists for the
subject before uploading files.
"""

from __future__ import annotations

from clinicedc_constants import YES
from django.utils import timezone
from rest_framework.test import APIClient

from edc_retinopathy.models import EyeExamRegister, SessionFile

from .mixins import RetinopathyTestCaseMixin


class ResolveSubjectTests(RetinopathyTestCaseMixin):
    """Tests for POST /api/retinopathy/resolve/"""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.eye_exam_register = self.create_eye_exam_register(self.rs)
        self.url = "/api/retinopathy/resolve/"

    # --- success ---

    def test_resolve_success(self) -> None:
        """Session exists → 200."""
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subject_identifier"], "105-10-0001-2")
        self.assertIn("eye_exam_register_id", response.data)

    def test_resolve_returns_eye_exam_register_id(self) -> None:
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.data["eye_exam_register_id"], self.eye_exam_register.pk)

    def test_resolve_returns_uploaded_list(self) -> None:
        """Response includes list of already-uploaded file types."""
        SessionFile.objects.create(
            eye_exam_register=self.eye_exam_register,
            file_type="left",
            original_filename="l.jpg",
            stored_filename=f"{self.eye_exam_register.pk}/l.jpg",
            capture_datetime=timezone.now(),
        )
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uploaded"], ["left"])

    def test_resolve_uploaded_empty_when_no_files(self) -> None:
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.data["uploaded"], [])

    # --- no session / ineligible ---

    def test_resolve_no_sessions_returns_404(self) -> None:
        self.eye_exam_register.delete()
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_resolve_all_complete_returns_400(self) -> None:
        for ft in self.eye_exam_register.expected_file_types:
            SessionFile.objects.create(
                eye_exam_register=self.eye_exam_register,
                file_type=ft,
                original_filename=f"{ft}.ext",
                stored_filename=f"{self.eye_exam_register.pk}/{ft}_stored.ext",
                capture_datetime=timezone.now(),
            )
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_eligible_session")

    def test_resolve_all_contraindicated_returns_400(self) -> None:
        EyeExamRegister.objects.filter(pk=self.eye_exam_register.pk).update(
            visual_impairment=YES,
        )
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_eligible_session")

    def test_resolve_skips_contraindicated(self) -> None:
        EyeExamRegister.objects.filter(pk=self.eye_exam_register.pk).update(
            visual_impairment=YES,
        )
        eligible = self.create_eye_exam_register(self.rs)
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["eye_exam_register_id"], eligible.pk)

    def test_resolve_skips_complete(self) -> None:
        for ft in self.eye_exam_register.expected_file_types:
            SessionFile.objects.create(
                eye_exam_register=self.eye_exam_register,
                file_type=ft,
                original_filename=f"{ft}.ext",
                stored_filename=f"{self.eye_exam_register.pk}/{ft}_stored.ext",
                capture_datetime=timezone.now(),
            )
        incomplete = self.create_eye_exam_register(self.rs)
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["eye_exam_register_id"], incomplete.pk)

    # --- required fields ---

    def test_resolve_missing_subject_identifier(self) -> None:
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    # --- auth ---

    def test_resolve_unauthenticated(self) -> None:
        client = APIClient()
        response = client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    # --- device_id ---

    def test_resolve_sets_device_id(self) -> None:
        self.assertEqual(self.eye_exam_register.device_id, "")
        self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2", "device_id": "CAM-001"},
            format="json",
        )
        self.eye_exam_register.refresh_from_db()
        self.assertEqual(self.eye_exam_register.device_id, "CAM-001")

    def test_resolve_does_not_overwrite_device_id(self) -> None:
        self.eye_exam_register.device_id = "CAM-001"
        self.eye_exam_register.save()
        self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2", "device_id": "CAM-999"},
            format="json",
        )
        self.eye_exam_register.refresh_from_db()
        self.assertEqual(self.eye_exam_register.device_id, "CAM-001")
