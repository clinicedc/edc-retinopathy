"""Tests for the resolve-subject endpoint."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ..models import RetinopathySession
from .models import RegisteredSubject


class ResolveSubjectTests(TestCase):
    """Tests for POST /api/retinopathy/resolve/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = User.objects.create_user(username="camera", password="pw")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.rs = RegisteredSubject.objects.create(
            subject_identifier="105-10-0001-2",
            initials="JD",
            gender="M",
            dob=date(1990, 6, 15),
        )
        self.url = "/api/retinopathy/resolve/"

    def test_resolve_success(self) -> None:
        """Valid subject data creates a session and returns 201."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": date.today().year - 1990,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["subject_identifier"], "105-10-0001-2"
        )
        self.assertIn("session_id", response.data)
        self.assertEqual(RetinopathySession.objects.count(), 1)

    def test_resolve_creates_session_with_metadata(self) -> None:
        """Session stores all camera-provided metadata."""
        self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": 35,
                "device_id": "CAM-001",
                "site_id": "SITE-A",
            },
            format="json",
        )
        session = RetinopathySession.objects.get()
        self.assertEqual(session.initials, "JD")
        self.assertEqual(session.sex, "M")
        self.assertEqual(session.age, 35)
        self.assertEqual(session.device_id, "CAM-001")
        self.assertEqual(session.site_id, "SITE-A")

    def test_resolve_unknown_subject(self) -> None:
        """Unknown subject_identifier returns 400."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "999-99-9999-9",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Subject identifier not found", response.data["errors"][0])
        self.assertEqual(RetinopathySession.objects.count(), 0)

    def test_resolve_initials_mismatch(self) -> None:
        """Mismatched initials returns 400."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "XX",
                "sex": "M",
                "age": date.today().year - 1990,
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
                "age": date.today().year - 1990,
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
        expected_age = (
            date.today().year
            - self.rs.dob.year
            - (
                (date.today().month, date.today().day)
                < (self.rs.dob.month, self.rs.dob.day)
            )
        )
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
                "age": expected_age + 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

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

    def test_resolve_case_insensitive_initials(self) -> None:
        """Initials comparison is case-insensitive."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "jd",
                "sex": "M",
                "age": date.today().year - 1990,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_resolve_case_insensitive_sex(self) -> None:
        """Sex comparison is case-insensitive."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "m",
                "age": date.today().year - 1990,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_resolve_optional_fields(self) -> None:
        """subject_identifier, initials, and sex are required; age,
        device_id, site_id are optional.
        """
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0001-2",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

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

    def test_resolve_multiple_sessions_allowed(self) -> None:
        """Same subject can have multiple sessions (repeat visits)."""
        for _ in range(3):
            response = self.client.post(
                self.url,
                {
                    "subject_identifier": "105-10-0001-2",
                    "initials": "JD",
                    "sex": "M",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(RetinopathySession.objects.count(), 3)

    def test_resolve_subject_without_dob(self) -> None:
        """Subject with null dob skips age validation."""
        RegisteredSubject.objects.create(
            subject_identifier="105-10-0002-3",
            initials="AB",
            gender="F",
            dob=None,
        )
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0002-3",
                "initials": "AB",
                "sex": "F",
                "age": 40,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_resolve_subject_without_initials(self) -> None:
        """Subject with blank initials skips initials validation."""
        RegisteredSubject.objects.create(
            subject_identifier="105-10-0003-4",
            initials="",
            gender="M",
        )
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "105-10-0003-4",
                "initials": "ZZ",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_resolve_error_code_subject_not_found(self) -> None:
        """Error response includes machine-readable code."""
        response = self.client.post(
            self.url,
            {
                "subject_identifier": "999-99-9999-9",
                "initials": "JD",
                "sex": "M",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "subject_not_found")

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
