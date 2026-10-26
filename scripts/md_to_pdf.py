"""Render a Markdown file to PDF (headings, paragraphs, bullet/numbered lists, tables, bold and code spans).

Usage: python scripts/md_to_pdf.py BUILD_GUIDE.md BUILD_GUIDE.pdf "TatvaAI build guide"
Used to keep BUILD_GUIDE.pdf and FEATURE_LIST.pdf in sync with their .md sources."""
import re
import sys
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def inline(text: str) -> str:
    t = escape(text)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8">\1</font>', t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)


def render(src: str, dst: str, title: str) -> None:
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10)
    heads = {1: ParagraphStyle("h1", parent=ss["Heading1"], fontSize=17, textColor=colors.HexColor("#0b3d66")),
             2: ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13, textColor=colors.HexColor("#0b3d66")),
             3: ParagraphStyle("h3", parent=ss["Heading3"], fontSize=11, textColor=colors.HexColor("#0b3d66"))}
    story, rows = [], []

    def flush_table():
        nonlocal rows
        if not rows:
            return
        data = [[Paragraph(inline(c), cell) for c in r] for r in rows]
        width = (A4[0] - 36 * mm) / len(rows[0])
        t = Table(data, colWidths=[width] * len(rows[0]), repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1fb")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d4e0")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([t, Spacer(1, 6)])
        rows = []

    for line in open(src, encoding="utf-8").read().splitlines():
        s = line.rstrip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                rows.append(cells)
            continue
        flush_table()
        if not s.strip() or s.strip() == "---":
            story.append(Spacer(1, 4))
        elif s.startswith("#"):
            level = min(len(s) - len(s.lstrip("#")), 3)
            story.append(Paragraph(inline(s.lstrip("# ")), heads[level]))
        elif re.match(r"^\s*([-*]|\d+\.)\s", s):
            story.append(Paragraph(inline(re.sub(r"^\s*([-*]|\d+\.)\s", "", s)), body, bulletText="\u2022" if s.lstrip()[0] in "-*" else s.lstrip().split(" ")[0]))
        else:
            story.append(Paragraph(inline(s.lstrip("> ")), body))
    flush_table()
    SimpleDocTemplate(dst, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=title).build(story)


if __name__ == "__main__":
    render(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "TatvaAI")
