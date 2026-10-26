"""Optional AI features, all off by default (FEATURE_* env flags) and imported lazily so the default install stays light.
Wired: OCR for scanned pages (PaddleOCR), PC counting in lab photos (YOLOv8), LLM rule drafting (Ollama).
Not wired in this build: LayoutLMv3 extraction, face matching of faculty photos, DocTamper, pgvector RAG, real satellite data."""
import io
import re

import httpx

from app.core.config import settings
from app.core.feature_flags import enabled

_ocr = None


def ocr_spans(png: bytes, w: float, h: float):
    """OCR one page image into spans {text, bbox} in page points; 'Label: value' lines are split at the colon so the anchor extractor works.
    Returns None when PaddleOCR is not installed (the caller then falls back to MANUAL_REVIEW_REQUIRED)."""
    global _ocr
    try:
        import numpy as np
        from paddleocr import PaddleOCR
        from PIL import Image
    except ImportError:
        return None
    _ocr = _ocr or PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    sx, sy = w / img.width, h / img.height
    spans = []
    for box, (text, _conf) in (_ocr.ocr(np.array(img), cls=False)[0] or []):
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        x0, y0, x1, y1 = min(xs) * sx, min(ys) * sy, max(xs) * sx, max(ys) * sy
        m = re.match(r"^(.+?:)\s+(.+)$", text)
        if m:  # split proportionally by character count
            cut = x0 + (x1 - x0) * len(m[1]) / len(text)
            spans += [dict(text=m[1], bbox=(x0, y0, cut, y1)), dict(text=m[2], bbox=(cut, y0, x1, y1))]
        else:
            spans.append(dict(text=text, bbox=(x0, y0, x1, y1)))
    return spans


def count_pcs(image_bytes: bytes) -> int | None:
    """YOLOv8 count of monitors/laptops in a lab photo, or None when FEATURE_YOLO is off or ultralytics is missing."""
    if not enabled("yolo"):
        return None
    try:
        from PIL import Image
        from ultralytics import YOLO
    except ImportError:
        return None
    res = YOLO("yolov8n.pt").predict(Image.open(io.BytesIO(image_bytes)), verbose=False)[0]
    return sum(res.names[int(c)] in ("tv", "laptop", "monitor") for c in res.boxes.cls)


def draft_rules_from_text(text: str) -> str:
    """FEATURE_LLM: ask a local Ollama model to draft Rule Pack YAML from pasted Handbook text. The result is only a suggestion:
    it is shown to the officer, who must validate and save it as a draft; nothing is stored or activated here."""
    prompt = ("Convert the following Handbook norm into one or more YAML rules for a rule pack. Each rule needs id, title, applies_to, type "
              "(formula|threshold|document_required|expiry|timeline|consistency|field_required), severity, message, citation{source,clause,page} "
              "and, for formulas, `let` and `check` expressions. Output YAML only.\n\n" + text[:6000])
    r = httpx.post(f"{settings.ollama_url}/api/generate", json={"model": settings.ollama_model, "prompt": prompt, "stream": False}, timeout=120)
    r.raise_for_status()
    return r.json().get("response", "")
