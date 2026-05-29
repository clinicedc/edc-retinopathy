"""Tests for Django system checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from edc_retinopathy.system_checks import storage_dir_check


class StorageDirCheckTests(TestCase):
    """Tests for the EDC_RETINOPATHY_STORAGE_DIR system check."""

    @override_settings(EDC_RETINOPATHY_STORAGE_DIR=None)
    def test_warning_when_not_set(self) -> None:
        errors = storage_dir_check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "edc_retinopathy.W001")

    @override_settings(EDC_RETINOPATHY_STORAGE_DIR="")
    def test_warning_when_empty(self) -> None:
        errors = storage_dir_check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "edc_retinopathy.W001")

    @override_settings(EDC_RETINOPATHY_STORAGE_DIR="/nonexistent/path/xyz")
    def test_error_when_dir_missing(self) -> None:
        errors = storage_dir_check()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].id, "edc_retinopathy.E001")

    def test_error_when_images_subdir_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.settings(EDC_RETINOPATHY_STORAGE_DIR=tmpdir):
                errors = storage_dir_check()
                self.assertEqual(len(errors), 1)
                self.assertEqual(errors[0].id, "edc_retinopathy.E002")

    def test_no_errors_when_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "images").mkdir()
            with self.settings(EDC_RETINOPATHY_STORAGE_DIR=tmpdir):
                errors = storage_dir_check()
                self.assertEqual(len(errors), 0)
