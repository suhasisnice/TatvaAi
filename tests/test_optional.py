"""Optional features stay off by default and degrade gracefully; the OCR hook is exercised with a fake OCR engine."""
import io
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]


def scanned_copy(pdf_path: Path) -> bytes:
    """Image-only PDF (no text layer) made from the rendering of a synthetic document."""
    src = pymupdf.open(pdf_path)
    png = src[0].get_pixmap(dpi=150).tobytes("png")
    out = pymupdf.open()
    page = out.new_page(width=src[0].rect.width, height=src[0].rect.height)
    page.insert_image(page.rect, stream=png)
    return out.tobytes()


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    import subprocess
    import sys

    out = tmp_path_factory.mktemp("syn")
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "e.json")], check=True, capture_output=True)
    return out / "a/2027-28/docs/TER_RECEIPT.pdf"


def test_flags_default_off():
    from app.core.feature_flags import enabled

    assert not any(enabled(f) for f in ("ocr", "layoutlm", "yolo", "face", "dtd", "llm", "rag", "real_geo"))


def test_scanned_page_without_ocr_needs_manual_review(sample):
    from app.services.extraction.fields import extract_pdf_fields

    fields = extract_pdf_fields(pymupdf.open(stream=scanned_copy(sample), filetype="pdf"))
    assert [(f["name"], f["status"]) for f in fields] == [("_page_text", "MANUAL_REVIEW_REQUIRED")]


def test_ocr_hook_extracts_fields_with_bbox(sample):
    """A fake OCR engine returns the words of the original page; the anchor extractor must produce the same fields from the scan."""
    from app.services.extraction.fields import extract_pdf_fields

    original = pymupdf.open(sample)
    truth = {f["name"]: f["value"] for f in extract_pdf_fields(original)}

    def fake_ocr(png, w, h):
        return [dict(text=s["text"], bbox=tuple(s["bbox"])) for b in original[0].get_text("dict")["blocks"] if b["type"] == 0 for ln in b["lines"] for s in ln["spans"] if s["text"].strip()]

    got = extract_pdf_fields(pymupdf.open(stream=scanned_copy(sample), filetype="pdf"), ocr=fake_ocr)
    assert {f["name"]: f["value"] for f in got} == truth
    assert all(0 <= f["bbox"][0] < f["bbox"][2] <= 1 and f["confidence"] < 0.99 for f in got)  # OCR is flagged as less certain


def test_missing_optional_libraries_do_not_break(sample):
    from app.services import optional

    assert optional.count_pcs(b"") is None  # FEATURE_YOLO off: returns before touching the image or importing ultralytics


def test_llm_draft_endpoint_is_off_by_default(client, login):
    r = client.post("/api/v1/rulepacks/draft-from-text", json={"text": "x"}, headers=login("officer@tatva.test"))
    assert r.status_code == 501 and "FEATURE_LLM" in r.json()["detail"]
