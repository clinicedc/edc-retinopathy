"""Tests for the DICOM review queue PDF report."""

from __future__ import annotations

from collections import Counter
from io import BytesIO

from django.utils import timezone

from edc_retinopathy.models import DmRetinopathyScreening, SessionFile
from edc_retinopathy.pdf_reports import ReviewQueueReport
from edc_retinopathy.pdf_reports.review_queue_pdf_report import (
    _review_status,
    _uploaded_label,
)

from .mixins import RetinopathyTestCaseMixin


class ReviewQueueReportTests(RetinopathyTestCaseMixin):
    """Tests for ReviewQueueReport."""

    def _add_dicom(self, camera_session, file_type: str) -> None:
        SessionFile.objects.create(
            camera_session=camera_session,
            file_type=file_type,
            original_filename=f"{file_type}.dcm",
            stored_filename=f"{camera_session.pk}_{file_type}.dcm",
            file_size=1024,
            capture_datetime=timezone.now(),
        )

    def test_uploaded_label(self) -> None:
        self.assertEqual(_uploaded_label(0, 0), "No")
        self.assertEqual(_uploaded_label(1, 0), "OD-ONLY")
        self.assertEqual(_uploaded_label(0, 1), "OS-ONLY")
        self.assertEqual(_uploaded_label(1, 1), "YES")

    def test_review_status(self) -> None:
        self.assertEqual(
            _review_status(reviewed=False, uploaded=False), "Awaiting results",
        )
        self.assertEqual(
            _review_status(reviewed=False, uploaded=True), "Ready for review",
        )
        self.assertEqual(_review_status(reviewed=True, uploaded=True), "Reviewed")
        self.assertEqual(_review_status(reviewed=True, uploaded=False), "Reviewed")

    def test_rows_cover_three_states_ordered_by_subject(self) -> None:
        # Awaiting results: no uploads.
        rs_awaiting = self.create_registered_subject("105-10-0003-4", initials="AA")
        self.create_camera_session(rs_awaiting)

        # Ready for review: dicoms uploaded, no screening.
        rs_ready = self.create_registered_subject("105-10-0002-3", initials="BB")
        ready_session = self.create_camera_session(rs_ready)
        self._add_dicom(ready_session, "right_dicom")

        # Reviewed: dicoms uploaded and a screening exists.
        rs_reviewed = self.create_registered_subject("105-10-0001-2", initials="CC")
        reviewed_session = self.create_camera_session(rs_reviewed)
        self._add_dicom(reviewed_session, "right_dicom")
        self._add_dicom(reviewed_session, "left_dicom")
        DmRetinopathyScreening.objects.create(camera_session=reviewed_session)

        rows = ReviewQueueReport()._build_rows()

        # Ordered by subject_identifier ascending.
        self.assertEqual(
            [row["subject_identifier"] for row in rows],
            ["105-10-0001-2", "105-10-0002-3", "105-10-0003-4"],
        )
        by_subject = {row["subject_identifier"]: row for row in rows}
        self.assertEqual(by_subject["105-10-0003-4"]["uploaded"], "No")
        self.assertEqual(by_subject["105-10-0003-4"]["review"], "Awaiting results")
        self.assertEqual(by_subject["105-10-0002-3"]["uploaded"], "OD-ONLY")
        self.assertEqual(by_subject["105-10-0002-3"]["review"], "Ready for review")
        self.assertEqual(by_subject["105-10-0001-2"]["uploaded"], "YES")
        self.assertEqual(by_subject["105-10-0001-2"]["review"], "Reviewed")

    def test_summary_counts(self) -> None:
        # Two awaiting, one ready, one reviewed -> total 4.
        self.create_camera_session(
            self.create_registered_subject("105-10-0004-5", initials="DD"),
        )
        self.create_camera_session(
            self.create_registered_subject("105-10-0003-4", initials="AA"),
        )
        ready = self.create_camera_session(
            self.create_registered_subject("105-10-0002-3", initials="BB"),
        )
        self._add_dicom(ready, "right_dicom")
        reviewed = self.create_camera_session(
            self.create_registered_subject("105-10-0001-2", initials="CC"),
        )
        self._add_dicom(reviewed, "right_dicom")
        self._add_dicom(reviewed, "left_dicom")
        DmRetinopathyScreening.objects.create(camera_session=reviewed)

        rows = ReviewQueueReport()._build_rows()
        uploaded_counts = Counter(row["uploaded"] for row in rows)
        review_counts = Counter(row["review"] for row in rows)

        self.assertEqual(uploaded_counts["No"], 2)
        self.assertEqual(uploaded_counts["OD-ONLY"], 1)
        self.assertEqual(uploaded_counts["YES"], 1)
        self.assertEqual(sum(uploaded_counts.values()), 4)

        self.assertEqual(review_counts["Awaiting results"], 2)
        self.assertEqual(review_counts["Ready for review"], 1)
        self.assertEqual(review_counts["Reviewed"], 1)
        self.assertEqual(sum(review_counts.values()), 4)

        # Summary flowables are appended (section title + two counts tables).
        self.assertEqual(len(ReviewQueueReport()._summary_flowables(rows)), 6)

    def test_report_builds_pdf(self) -> None:
        rs = self.create_registered_subject()
        session = self.create_camera_session(rs)
        self._add_dicom(session, "right_dicom")
        self._add_dicom(session, "left_dicom")

        buffer = BytesIO()
        ReviewQueueReport().build(buffer)
        data = buffer.getvalue()

        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 1000)

    def test_report_builds_pdf_when_empty(self) -> None:
        buffer = BytesIO()
        ReviewQueueReport().build(buffer)
        self.assertTrue(buffer.getvalue().startswith(b"%PDF"))
