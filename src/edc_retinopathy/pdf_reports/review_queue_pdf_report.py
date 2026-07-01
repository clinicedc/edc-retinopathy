from __future__ import annotations

from collections import Counter

from django.contrib.sites.models import Site
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone
from django.utils.timezone import localtime
from edc_pdf_reports import Report
from edc_protocol.research_protocol_config import ResearchProtocolConfig
from edc_sites.site import sites
from edc_utils.date import to_local
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import CameraSession, DmRetinopathyScreening, SessionFile

_TITLE = "DICOM Review Queue"

_HEADER_STYLE = ParagraphStyle(
    "col_header", fontSize=8, alignment=TA_LEFT, fontName="Helvetica-Bold",
)
_CELL_STYLE = ParagraphStyle("cell", fontSize=7, alignment=TA_LEFT, leading=9)
_CELL_RIGHT = ParagraphStyle("cell_r", fontSize=7, alignment=TA_RIGHT, leading=9)
_SECTION_STYLE = ParagraphStyle(
    "section", fontSize=10, alignment=TA_LEFT, fontName="Helvetica-Bold",
)
_ALT_ROW = colors.Color(0.95, 0.95, 0.95)

# Fixed display order for the end-of-report value counts.
_UPLOADED_ORDER = ("No", "OS-ONLY", "OD-ONLY", "YES")
_REVIEW_ORDER = ("Awaiting results", "Ready for review", "Reviewed")


def _uploaded_label(od_count: int, os_count: int) -> str:
    """Return the four-state upload label matching the review queue table."""
    if od_count and os_count:
        return "YES"
    if od_count:
        return "OD-ONLY"
    if os_count:
        return "OS-ONLY"
    return "No"


def _review_status(*, reviewed: bool, uploaded: bool) -> str:
    """Return the review-column status for a session."""
    if reviewed:
        return "Reviewed"
    if uploaded:
        return "Ready for review"
    return "Awaiting results"


class ReviewQueueReport(Report):
    """PDF of the DICOM review queue, for distribution by email.

    Covers all camera sessions (ordered by subject_identifier) so that the
    "Reviewed" status can be shown alongside those awaiting or ready for review.
    Every page carries the trial name and CONFIDENTIAL in the header and footer.
    """

    def __init__(self, **kwargs):
        self.protocol_name = ResearchProtocolConfig().protocol_name
        super().__init__(**kwargs)

    def on_first_page(self, canvas, doc):
        self.draw_header(canvas, doc)
        self.draw_footer(canvas, doc)

    def draw_header(self, canvas, doc):  # noqa: ARG002
        width, height = self.page.get("pagesize")
        canvas.setFontSize(8)
        canvas.drawString(35, height - 25, self.protocol_name.upper())
        canvas.drawRightString(width - 35, height - 25, "CONFIDENTIAL")

    def draw_footer(self, canvas, doc):  # noqa: ARG002
        width, _ = self.page.get("pagesize")
        canvas.setFontSize(6)
        timestamp = to_local(timezone.now()).strftime("%Y-%m-%d %H:%M")
        canvas.drawString(35, self.footer_row_height, self.protocol_name.upper())
        # Sit CONFIDENTIAL above the centred "Page x of y" drawn by NumberedCanvas.
        canvas.drawCentredString(width / 2.0, self.footer_row_height + 10, "CONFIDENTIAL")
        canvas.drawRightString(
            width - 35, self.footer_row_height, f"printed on {timestamp}",
        )

    def get_report_story(self, document_template: SimpleDocTemplate = None, **kwargs):  # noqa: ARG002
        story = [
            Table([[
                Paragraph(
                    _TITLE.upper(),
                    ParagraphStyle(
                        "title", fontSize=11, alignment=TA_LEFT, fontName="Helvetica-Bold",
                    ),
                ),
                Paragraph(
                    self.protocol_name.upper(),
                    ParagraphStyle(
                        "title_r", fontSize=11, alignment=TA_RIGHT, fontName="Helvetica-Bold",
                    ),
                ),
            ]]),
            Spacer(0.1 * cm, 0.4 * cm),
        ]
        rows = self._build_rows()
        if not rows:
            story.append(Paragraph("No sessions found.", _CELL_STYLE))
            return story
        story.append(self._table(rows))
        story.extend(self._summary_flowables(rows))
        return story

    def _summary_flowables(self, rows: list[dict]) -> list:
        """Value counts (with totals) for the Site, Uploaded and Review columns."""
        uploaded_counts = Counter(row["uploaded"] for row in rows)
        review_counts = Counter(row["review"] for row in rows)
        site_counts = Counter(row["site"] or "(no site)" for row in rows)
        site_order = tuple(sorted(site_counts))
        total = len(rows)
        return [
            Spacer(0.1 * cm, 0.6 * cm),
            Paragraph("Summary", _SECTION_STYLE),
            Spacer(0.1 * cm, 0.25 * cm),
            self._counts_table("Site", site_order, site_counts, total),
            Spacer(0.1 * cm, 0.35 * cm),
            self._counts_table("Uploaded", _UPLOADED_ORDER, uploaded_counts, total),
            Spacer(0.1 * cm, 0.35 * cm),
            self._counts_table("Review", _REVIEW_ORDER, review_counts, total),
        ]

    @staticmethod
    def _counts_table(
        title: str, order: tuple[str, ...], counts: Counter, total: int,
    ) -> Table:
        data = [[Paragraph(title, _HEADER_STYLE), Paragraph("Count", _HEADER_STYLE)]]
        data += [
            [Paragraph(key, _CELL_STYLE), Paragraph(str(counts.get(key, 0)), _CELL_RIGHT)]
            for key in order
        ]
        data.append([Paragraph("Total", _HEADER_STYLE), Paragraph(str(total), _HEADER_STYLE)])
        table = Table(data, colWidths=[4.5 * cm, 2.0 * cm])
        last = len(data) - 1
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, last), (-1, last), "Helvetica-Bold"),
            ("BACKGROUND", (0, last), (-1, last), _ALT_ROW),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        return table

    def _build_rows(self) -> list[dict]:
        has_dicoms = Exists(
            SessionFile.objects.filter(
                camera_session=OuterRef("pk"),
                file_type__in=("left_dicom", "right_dicom"),
            ),
        )
        has_screening = Exists(
            DmRetinopathyScreening.objects.filter(camera_session=OuterRef("pk")),
        )
        queryset = CameraSession.objects.annotate(
            uploaded=has_dicoms,
            reviewed=has_screening,
            od_dicom_count=Count("files", filter=Q(files__file_type="right_dicom")),
            os_dicom_count=Count("files", filter=Q(files__file_type="left_dicom")),
        ).order_by("subject_identifier", "-report_datetime")

        site_titles = {site.id: sites.get(site.id).title for site in Site.objects.all()}
        return [
            {
                "subject_identifier": session.subject_identifier or "",
                "site": site_titles.get(session.site_id, ""),
                "report_datetime": localtime(session.report_datetime).strftime(
                    "%Y-%m-%d %H:%M",
                ),
                "uploaded": _uploaded_label(
                    session.od_dicom_count, session.os_dicom_count,
                ),
                "od": str(session.od_dicom_count),
                "os": str(session.os_dicom_count),
                "review": _review_status(
                    reviewed=session.reviewed, uploaded=session.uploaded,
                ),
            }
            for session in queryset
        ]

    @staticmethod
    def _table(rows: list[dict]) -> Table:
        col_widths = [
            3.5 * cm, 3.5 * cm, 3.0 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm, 3.5 * cm,
        ]
        header = [
            Paragraph("Subject", _HEADER_STYLE),
            Paragraph("Site", _HEADER_STYLE),
            Paragraph("Session date", _HEADER_STYLE),
            Paragraph("Uploaded", _HEADER_STYLE),
            Paragraph("OD", _HEADER_STYLE),
            Paragraph("OS", _HEADER_STYLE),
            Paragraph("Review", _HEADER_STYLE),
        ]
        data = [header, *(
            [
                Paragraph(row["subject_identifier"], _CELL_STYLE),
                Paragraph(row["site"], _CELL_STYLE),
                Paragraph(row["report_datetime"], _CELL_STYLE),
                Paragraph(row["uploaded"], _CELL_STYLE),
                Paragraph(row["od"], _CELL_STYLE),
                Paragraph(row["os"], _CELL_STYLE),
                Paragraph(row["review"], _CELL_STYLE),
            ]
            for row in rows
        )]
        table = Table(data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ALT_ROW]),
        ]))
        return table
