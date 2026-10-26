"""Validation report PDF for one application (reportlab)."""
import hashlib
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Application, Document, Flag, Verification

TIER_COLOR = {"GREEN": "#1a8a4a", "AMBER": "#b4720a", "RED": "#c4293a"}
TIER_LABEL = {"GREEN": "No risk", "AMBER": "Medium risk", "RED": "High risk"}
SEV_ORDER = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
DISCLAIMER = ("Decision support only. This report lists findings with their evidence; it does not approve, "
              "reject or penalise anyone. Final decisions rest with competent AICTE authorities. "
              "All data in this prototype is synthetic and every external source is a MOCK.")


def build_report(app: Application, documents: list[Document], flags: list[Flag],
                 verifications: list[Verification]) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"Validation report - application {app.id}")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, textColor=colors.HexColor("#0b3d66"), spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=colors.HexColor("#0b3d66"), spaceBefore=12, spaceAfter=4, keepWithNext=1)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#5b6b7c"))

    def P(text, style=body):
        return Paragraph(escape(str(text)), style)

    story = [
        Paragraph("TatvaAI &mdash; Validation report", h1),
        P(f"{app.institution.name} | {app.institution.state} | {app.institution.aicte_id}", small),
        P(f"{app.category} | AY {app.academic_year} | Status {app.status} | Generated {datetime.utcnow():%Y-%m-%d %H:%M} UTC", small),
        Spacer(1, 8),
    ]

    tier = app.risk_tier or "N/A"
    tier_hex = TIER_COLOR.get(tier, "#777777")
    box = Table([[Paragraph(f'<font color="white"><b>{tier}</b> &middot; {TIER_LABEL.get(tier, "Not scored")}</font>', body),
                  P(f"Risk score {app.risk_score}")]], colWidths=[70 * mm, 50 * mm])
    box.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor(tier_hex)),
                             ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e3ee")),
                             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 8)]))
    story.append(box)

    story.append(Paragraph("Top reasons", h2))
    if app.top_reasons:
        for r in app.top_reasons:
            story.append(P(f"- {r}"))
    else:
        story.append(P("No findings need attention."))

    story.append(Paragraph("Documents", h2))
    rows = [["Type", "File", "Signature", "SHA-256"]]
    for d in documents:
        rows.append([P(d.doc_type.replace("_", " ").title(), small), P(d.file_name, small),
                     P(d.signature_status, small), P(d.sha256[:16], small)])
    t = Table(rows, colWidths=[42 * mm, 52 * mm, 34 * mm, 36 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1fb")),
                           ("FONTSIZE", (0, 0), (-1, 0), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e3ee")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)

    story.append(Paragraph(f"Findings ({len(flags)})", h2))
    for f in sorted(flags, key=lambda x: (SEV_ORDER.get(x.severity, 9), x.code)):
        tag = " - PRELIMINARY INDICATOR (requires human verification)" if f.forensic else ""
        story.append(Paragraph(f"<b>{escape(f.severity)}</b> &middot; {escape(f.code)} &middot; {escape(f.engine)}{escape(tag)}", body))
        story.append(P(f.message))
        if f.explanation:
            story.append(P(f.explanation, small))
        if f.citation:
            story.append(P(f"Citation: {f.citation}", small))
        decision = f"Officer: {f.status}" + (f" - {f.decision_reason}" if f.decision_reason else "")
        story.append(P(decision, small))
        if f.inspection_status and f.inspection_status != "PENDING":
            story.append(P(f"Inspection: {f.inspection_status} by {f.inspection_by} - {f.inspection_note}", small))
        story.append(Spacer(1, 5))
    if not flags:
        story.append(P("No findings."))

    story.append(Paragraph("Issuer verification", h2))
    if verifications:
        vrows = [["Source", "Status", "Summary"]]
        for v in verifications:
            vrows.append([P(v.source_name, small), P(v.status, small), P(v.manual_note and f"Manually confirmed: {v.manual_note}" or v.summary, small)])
        vt = Table(vrows, colWidths=[50 * mm, 40 * mm, 74 * mm], repeatRows=1)
        vt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1fb")),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e3ee")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(vt)
    else:
        story.append(P("No issuer checks recorded."))

    story += [Spacer(1, 14), P(DISCLAIMER, small)]

    digest = hashlib.sha256(
        "|".join([str(app.id), str(app.risk_score), str(app.risk_tier)] + sorted(f.fingerprint for f in flags)).encode()
    ).hexdigest()

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#5b6b7c"))
        canvas.drawString(18 * mm, 10 * mm, f"Content SHA-256: {digest}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
