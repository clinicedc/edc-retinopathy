"""Tests for the resolve-subject endpoint.

The camera calls resolve to find a pre-existing CameraSession (created
by the clinician in the EDC) and validate demographics before uploading.
"""

from __future__ import annotations

from clinicedc_constants import YES
from django.utils import timezone
from rest_framework.test import APIClient

from edc_retinopathy.models import CameraSession, SessionFile

from .mixins import RetinopathyTestCaseMixin


class ResolveSubjectTests(RetinopathyTestCaseMixin):
    """Tests for POST /api/retinopathy/resolve/"""

    def setUp(self) -> None:
        super().setUp()
        self.rs = self.create_registered_subject()
        self.camera_session = self.create_camera_session(self.rs)
        self.url = "/api/retinopathy/resolve/"

    # --- success ---

    def test_resolve_success(self) -> None:
        """Session exists and demographics match → 200."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": self.camera_session.age_in_years,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subject_identifier"], "105-10-0001-2")
        self.assertIn("camera_session_id", response.data)

    def test_resolve_returns_camera_session_id(self) -> None:
        """Response camera_session_id matches the pre-created session."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["camera_session_id"], self.camera_session.pk)

    def test_resolve_reactivated_false_no_uploads(self) -> None:
        """Reactivated is False when session has no uploads."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["reactivated"])

    def test_resolve_reactivated_true_with_uploads(self) -> None:
        """Reactivated is True when session already has uploads."""
        SessionFile.objects.create(
            camera_session=self.camera_session,
            file_type="left",
            original_filename="l.jpg",
            stored_filename="aaa.jpg",
            capture_datetime=timezone.now(),
        )
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["reactivated"])

    # --- no session / ineligible ---

    def test_resolve_no_sessions_returns_404(self) -> None:
        """No CameraSession for subject returns 404."""
        self.camera_session.delete()
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "no_session")

    def test_resolve_all_complete_returns_400(self) -> None:
        """All sessions complete → 400 with no_eligible_session."""
        for ft in self.camera_session.expected_file_types:
            SessionFile.objects.create(
                camera_session=self.camera_session,
                file_type=ft,
                original_filename=f"{ft}.ext",
                stored_filename=f"{ft}_stored.ext",
                capture_datetime=timezone.now(),
            )
        self.assertTrue(self.camera_session.is_complete)
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_eligible_session")

    def test_resolve_all_contraindicated_returns_400(self) -> None:
        """All sessions contraindicated → 400."""
        CameraSession.objects.filter(pk=self.camera_session.pk).update(
            visual_impairment=YES,
        )
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "no_eligible_session")

    def test_resolve_skips_contraindicated(self) -> None:
        """Resolve skips contraindicated sessions, finds eligible one."""
        CameraSession.objects.filter(pk=self.camera_session.pk).update(
            visual_impairment=YES,
        )
        eligible = self.create_camera_session(self.rs)
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["camera_session_id"], eligible.pk)

    def test_resolve_skips_complete(self) -> None:
        """Resolve skips complete sessions, finds incomplete one."""
        for ft in self.camera_session.expected_file_types:
            SessionFile.objects.create(
                camera_session=self.camera_session,
                file_type=ft,
                original_filename=f"{ft}.ext",
                stored_filename=f"{ft}_stored.ext",
                capture_datetime=timezone.now(),
            )
        incomplete = self.create_camera_session(self.rs)
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["camera_session_id"], incomplete.pk)

    # --- demographic validation ---

    def test_resolve_initials_mismatch(self) -> None:
        """Mismatched initials returns 400."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "XX",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Initials mismatch", response.data["errors"][0])

    def test_resolve_sex_mismatch(self) -> None:
        """Mismatched sex returns 400."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "F",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Sex mismatch", response.data["errors"][0])

    def test_resolve_age_mismatch(self) -> None:
        """Age difference > 1 year returns 400."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": 99,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Age mismatch", response.data["errors"][0])

    def test_resolve_age_off_by_one_accepted(self) -> None:
        """Age difference of exactly 1 year is accepted (birthday boundary)."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": self.camera_session.age_in_years + 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_resolve_multiple_errors(self) -> None:
        """Multiple mismatches return all errors."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "XX",
                "sex": "F",
                "age": 99,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(response.data["errors"]), 3)

    def test_resolve_error_code_validation_mismatch(self) -> None:
        """Validation mismatch includes the correct code."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "XX",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "validation_mismatch")

    # --- case sensitivity ---

    def test_resolve_case_insensitive_initials(self) -> None:
        """Initials comparison is case-insensitive."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "jd",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_resolve_case_insensitive_sex(self) -> None:
        """Sex comparison is case-insensitive."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "m",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    # --- optional / required fields ---

    def test_resolve_optional_age(self) -> None:
        """Age is optional; resolve succeeds without it."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_resolve_missing_initials(self) -> None:
        """Missing initials returns 400 validation error."""
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2", "sex": "M"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_resolve_missing_sex(self) -> None:
        """Missing sex returns 400 validation error."""
        response = self.client.post(
            self.url,
            {"subject_identifier": "105-10-0001-2", "initials": "JD"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_resolve_missing_subject_identifier(self) -> None:
        """Missing subject_identifier returns 400 validation error."""
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_resolve_invalid_sex_value(self) -> None:
        """Sex must be M or F; other values are rejected."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "Male",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    # --- auth ---

    def test_resolve_unauthenticated(self) -> None:
        """Request without token returns 401."""
        client = APIClient()
        response = client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    # --- device_id ---

    def test_resolve_sets_device_id(self) -> None:
        """device_id is set on the session when absent."""
        self.assertEqual(self.camera_session.device_id, "")
        self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "device_id": "CAM-001",
            },
            format="json",
        )
        self.camera_session.refresh_from_db()
        self.assertEqual(self.camera_session.device_id, "CAM-001")

    def test_resolve_does_not_overwrite_device_id(self) -> None:
        """Existing device_id is not overwritten by a second resolve."""
        self.camera_session.device_id = "CAM-001"
        self.camera_session.save()
        self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "device_id": "CAM-999",
            },
            format="json",
        )
        self.camera_session.refresh_from_db()
        self.assertEqual(self.camera_session.device_id, "CAM-001")
