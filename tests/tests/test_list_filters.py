"""Tests for the `EyeExamRegisterAdmin` changelist list filters."""

from __future__ import annotations

from django.test.client import RequestFactory

from edc_retinopathy.admin.list_filters import FileCountListFilter
from edc_retinopathy.constants import LEFT_DICOM, REPORT, RIGHT_DICOM
from edc_retinopathy.models import EyeExamRegister

from .mixins import RetinopathyTestCaseMixin


class FileCountListFilterTests(RetinopathyTestCaseMixin):
    def setUp(self) -> None:
        super().setUp()
        self.none = self.create_eye_exam_register(
            self.create_registered_subject(subject_identifier="105-10-0001-2"),
        )
        self.one = self.create_eye_exam_register(
            self.create_registered_subject(subject_identifier="105-10-0002-0"),
        )
        self.create_session_file(self.one, LEFT_DICOM)
        self.three = self.create_eye_exam_register(
            self.create_registered_subject(subject_identifier="105-10-0003-9"),
        )
        for file_type in [LEFT_DICOM, RIGHT_DICOM, REPORT]:
            self.create_session_file(self.three, file_type)

    @staticmethod
    def filtered(value: str | None) -> list[EyeExamRegister]:
        params = {} if value is None else {FileCountListFilter.parameter_name: [value]}
        list_filter = FileCountListFilter(
            request=RequestFactory().get("/"),
            params=params,
            model=EyeExamRegister,
            model_admin=None,
        )
        queryset = list_filter.queryset(None, EyeExamRegister.objects.all())
        return list(queryset.order_by("created"))

    def test_lookups(self) -> None:
        list_filter = FileCountListFilter(
            request=RequestFactory().get("/"),
            params={},
            model=EyeExamRegister,
            model_admin=None,
        )
        self.assertEqual(
            [value for value, _ in list_filter.lookups(None, None)],
            ["0", "1", "2", "3", "4+"],
        )

    def test_no_value_does_not_filter(self) -> None:
        self.assertEqual(self.filtered(None), [self.none, self.one, self.three])

    def test_unrecognized_value_does_not_filter(self) -> None:
        self.assertEqual(self.filtered("blah"), [self.none, self.one, self.three])
        self.assertEqual(self.filtered("99"), [self.none, self.one, self.three])

    def test_filters_on_zero_files(self) -> None:
        self.assertEqual(self.filtered("0"), [self.none])

    def test_filters_on_exact_count(self) -> None:
        self.assertEqual(self.filtered("1"), [self.one])
        self.assertEqual(self.filtered("2"), [])
        self.assertEqual(self.filtered("3"), [self.three])

    def test_filters_on_max_count_or_more(self) -> None:
        self.assertEqual(self.filtered("4+"), [])
        for index in range(2):
            self.create_session_file(self.one, REPORT, original_filename=f"x{index}.ext")
        self.create_session_file(self.one, RIGHT_DICOM)
        self.assertEqual(self.filtered("4+"), [self.one])
