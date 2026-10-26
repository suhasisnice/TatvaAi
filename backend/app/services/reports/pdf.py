"""PDF reports (ReportLab): per-application validation report and the ranked inspection checklist.
The footer prints a SHA-256 of the report content (rendered with a placeholder footer); the audit log records the SHA-256 of the final file."""
import copy
import hashlib
import io
import json
from datetime import datetime, timezone

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.models import Application, Document, DocumentPage, Flag, FlagDecision, Institution, Verification
from app.services.risk.scoring import ROUTING, ROUTING_TEXT, TIER_LABEL

NAVY = colors.HexColor("#1F3864")
TIER_COLOR = {"GREEN": colors.HexColor("#2E7D5B"), "AMBER": colors.HexColor("#F2A93B"), "RED": colors.HexColor("#C0392B")}
SS = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=SS["BodyText"], fontSize=8.5, leading=11)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=7.5, leading=9.5, textColor=colors.HexColor("#444444"))
H1 = ParagraphStyle("h1", parent=SS["Title"], fontSize=18, textColor=NAVY, alignment=0)
H2 = ParagraphStyle("h2", parent=SS["Heading2"], fontSize=12, textColor=NAVY, spaceBefore=10, keepWithNext=0)
DISCLAIMER = "Decision support only. Final decisions rest with competent AICTE authorities. All data in this prototype is synthetic; external sources are MOCK."
P = lambda t, st=BODY: Paragraph(str(t).replace("&", "&amp;").replace("<", "&lt;"), st)


def _build(story: list, digest: str, title: str) -> bytes:
    buf = io.BytesIO()

    def footer(c, doc):
        c.saveState()
        c.setFont("Helvetica", 6.5)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(15 * mm, 9 * mm, f"Report SHA-256 (content): {digest}")
        c.drawRightString(A4[0] - 15 * mm, 9 * mm, f"{title} - page {doc.page}")
        c.drawString(15 * mm, 13 * mm, DISCLAIMER[:150])
        c.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=18 * mm, title=title, author="PramaanAI", invariant=1).build(
        copy.deepcopy(list(story)), onFirstPage=footer, onLaterPages=footer)  # flowables are mutated while laying out, so each pass gets fresh copies
    return buf.getvalue()


def render(story: list, title: str) -> tuple[bytes, str]:
    digest = hashlib.sha256(_build(story, "(computed over the content of this report)", title)).hexdigest()
    return _build(story, digest, title), digest


def _table(rows, widths, header=True, extra=None):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _tier_box(tier: str, score) -> Table:
    t = Table([[f"{tier} - {TIER_LABEL.get(tier, 'Not scored')}", f"Score {score}"]], colWidths=[100 * mm, 50 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TIER_COLOR.get(tier, colors.grey)), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white if tier != "AMBER" else colors.black),
                           ("FONTSIZE", (0, 0), (-1, -1), 13), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 8)]))
    return t


def _thumb(db: Session, ev: dict, width_mm: float = 55):
    """Crop of the document page around the evidence bounding box, with the box drawn in red."""
    if not ev.get("document_id") or not ev.get("bbox"):
        return None
    pg = db.scalar(select(DocumentPage).where(DocumentPage.document_id == ev["document_id"], DocumentPage.page_no == (ev.get("page") or 1)))
    if not pg:
        return None
    try:
        im = Image.open(io.BytesIO(storage.get(pg.image_key))).convert("RGB")
    except Exception:
        return None
    W, H = im.size
    x0, y0, x1, y1 = ev["bbox"]
    ImageDraw.Draw(im).rectangle([x0 * W - 3, y0 * H - 3, x1 * W + 3, y1 * H + 3], outline=(192, 57, 43), width=4)
    crop = im.crop((max(0, int((x0 - 0.45) * W)), max(0, int((y0 - 0.04) * H)), min(W, int((x1 + 0.1) * W)), min(H, int((y1 + 0.04) * H))))
    out = io.BytesIO()
    crop.save(out, format="PNG")
    out.seek(0)
    w = width_mm * mm
    return RLImage(out, width=w, height=w * crop.size[1] / crop.size[0])


def application_report(db: Session, app: Application) -> tuple[bytes, str]:
    inst = db.get(Institution, app.institution_id)
    flags = list(db.scalars(select(Flag).where(Flag.application_id == app.id).order_by(Flag.id)))
    sev_rank = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
    flags.sort(key=lambda f: (sev_rank[f.severity], f.id))
    tier = app.risk_tier or "UNSCORED"
    reasons = json.loads(app.risk_reasons or "[]")
    s = [P("PramaanAI Validation Report", H1), P(DISCLAIMER, SMALL), Spacer(1, 4 * mm)]
    s.append(_table([["Institution", inst.name], ["AICTE ID (synthetic)", inst.aicte_id or "-"], ["State", inst.state], ["Application", f"#{app.id} - {app.category} - AY {app.academic_year}"],
                     ["Status", f"{app.status}{' (locked)' if app.locked else ''}"], ["Rule Pack version", app.rule_pack_version or "-"],
                     ["Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")]], [45 * mm, 135 * mm], header=False))
    s += [Spacer(1, 4 * mm), _tier_box(tier, app.risk_score)]
    if app.risk_tier:
        s += [Spacer(1, 2 * mm), P(f"Routing: {ROUTING_TEXT[ROUTING[tier]]}. GREEN = no risk, AMBER = medium risk, RED = high risk. The tier is advice to the officer, not a decision.")]
    s.append(P("Top reasons", H2))
    s.append(_table([["Finding", "Severity", "Contribution"]] + ([[P(r["message"]), r["severity"], r["contribution"]] for r in reasons] or [["No findings", "", ""]]), [120 * mm, 30 * mm, 30 * mm]))

    s.append(P("Documents and proof levels", H2))
    docs = list(db.scalars(select(Document).where(Document.application_id == app.id).order_by(Document.id)))
    s.append(_table([["#", "Type", "Signature", "Proof level", "SHA-256"]] + [[d.id, d.doc_type, d.dsc_status, d.proof_level or "-", d.sha256[:16] + "..."] for d in docs], [10 * mm, 60 * mm, 38 * mm, 36 * mm, 36 * mm]))

    s.append(P(f"Flags with evidence ({sum(f.severity != 'INFO' for f in flags)} findings, {sum(f.severity == 'INFO' for f in flags)} notices)", H2))
    for f in flags:
        ev, c = json.loads(f.evidence), (json.loads(f.citation) if f.citation else None)
        head = f"{f.severity} - {f.code} ({f.engine}){' - PRELIMINARY INDICATOR, requires human verification' if f.forensic else ''} - status {f.status}"
        block = [P(head, ParagraphStyle("fh", parent=BODY, fontName="Helvetica-Bold")), P(f.message)]
        if f.explanation:
            block.append(P(f.explanation, SMALL))
        if c:
            block.append(P(f"Citation: {c['source']}, {c['clause']}, p. {c['page']} (rule {f.rule_id}, pack {f.rule_pack_version})", SMALL))
        refs = [f"doc #{e['document_id']} p.{e.get('page') or 1}" + (f" [{e['field']}]" if e.get("field") else "") if e.get("document_id") else f"{e.get('system_source')} ({e.get('record_id')})" for e in ev]
        block.append(P("Evidence: " + "; ".join(refs), SMALL))
        thumbs = [t for t in (_thumb(db, e) for e in ev[:3]) if t]
        if thumbs and f.severity != "INFO":
            block.append(Table([thumbs], colWidths=[58 * mm] * len(thumbs)))
        for d in db.scalars(select(FlagDecision).where(FlagDecision.flag_id == f.id)):
            block.append(P(f"Officer decision: {d.decision} - {d.reason} ({d.decided_at:%Y-%m-%d})", SMALL))
        block.append(Spacer(1, 2.5 * mm))
        s += block

    s.append(P("Verification log", H2))
    vs = list(db.scalars(select(Verification).where(Verification.application_id == app.id).order_by(Verification.id)))
    s.append(_table([["Source (MOCK)", "Status", "Detail", "Checked"]] + [[P(v.source, SMALL), v.status, P(v.response_summary or "", SMALL), f"{v.checked_at:%Y-%m-%d}"] for v in vs], [48 * mm, 38 * mm, 70 * mm, 24 * mm]))
    return render(s, f"Validation report - application {app.id}")


def inspection_pdf(items: list[dict]) -> bytes:
    s = [P("Risk-targeted inspection list", H1), P(DISCLAIMER, SMALL), P("Ranked by risk score. Applications listed here are RED = high risk; reasons and an on-site checklist follow each entry.", BODY), Spacer(1, 3 * mm)]
    for i in items:
        s.append(_tier_box(i["tier"], i["score"]))
        s.append(P(f"#{i['rank']}  {i['institution_name']} - {i['state']} - {i['category']} AY {i['academic_year']} (application {i['application_id']}, pack {i['rule_pack_version']})",
                   ParagraphStyle("ih", parent=BODY, fontName="Helvetica-Bold", spaceBefore=3)))
        s.append(P("Why this institution", H2))
        s += [P(f"- {r['message']} ({r['severity']})") for r in i["reasons"]]
        s.append(P("On-site checklist", H2))
        s += [P(f"[  ]  {c['check']}  (finding: {c['finding']})") for c in i["checklist"]]
        s.append(Spacer(1, 6 * mm))
    if not items:
        s.append(P("No RED applications at this time."))
    return render(s, "Inspection list")[0]
