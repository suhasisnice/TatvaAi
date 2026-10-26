"""PDF digital-signature inspection (pyHanko) and PDF metadata."""
import io
import logging
from pathlib import Path

import pymupdf

from app.core.config import settings

logging.getLogger("pyhanko.sign.diff_analysis").setLevel(logging.CRITICAL)  # modified docs log a noisy traceback by design


def _trust_context(moment):
    from pyhanko.keys import load_cert_from_pemder
    from pyhanko_certvalidator import ValidationContext

    p = Path(settings.trust_root_path)
    roots = [load_cert_from_pemder(str(p))] if p.exists() else []
    return ValidationContext(trust_roots=roots, allow_fetching=False, moment=moment)


def signature_info(data: bytes) -> dict:
    """status: UNSIGNED | SIGNED_VALID | SIGNED_MODIFIED | SIGNED_INVALID | SIGNED_UNTRUSTED."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    d = pymupdf.open(stream=data, filetype="pdf")
    m = d.metadata or {}
    meta = {k: m.get(k) for k in ("creationDate", "modDate", "producer", "creator", "title")}
    sigs = PdfFileReader(io.BytesIO(data)).embedded_signatures
    if not sigs:
        return dict(status="UNSIGNED", signatures=[], pdf_meta=meta)
    infos = []
    for sig in sigs:
        try:
            st = validate_pdf_signature(sig, _trust_context(sig.self_reported_timestamp))
            modified = st.coverage.name != "ENTIRE_FILE" and st.modification_level is not None and st.modification_level.name not in ("NONE", "LTA_UPDATES")
            infos.append(dict(field=sig.field_name, signer=sig.signer_cert.subject.human_friendly, signed_at=st.signer_reported_dt.isoformat() if st.signer_reported_dt else None,
                              intact=bool(st.intact), valid=bool(st.valid), trusted=bool(st.trusted), coverage=st.coverage.name,
                              modification_level=st.modification_level.name if st.modification_level else None, modified_after_signing=modified))
        except Exception as e:  # unparsable / corrupt signature is itself evidence
            infos.append(dict(field=sig.field_name, signer=None, signed_at=None, intact=False, valid=False, trusted=False, coverage=None,
                              modification_level=None, modified_after_signing=False, error=str(e)[:200]))
    bad = [i for i in infos if not (i["intact"] and i["valid"])]
    status = ("SIGNED_INVALID" if bad else "SIGNED_MODIFIED" if any(i["modified_after_signing"] for i in infos)
              else "SIGNED_UNTRUSTED" if not all(i["trusted"] for i in infos) else "SIGNED_VALID")
    return dict(status=status, signatures=infos, pdf_meta=meta)


def signed_revision(data: bytes) -> bytes | None:
    """The bytes of the PDF exactly as signed (up to the end of the first signature's byte range), to see what changed afterwards."""
    from pyhanko.pdf_utils.reader import PdfFileReader

    sigs = PdfFileReader(io.BytesIO(data)).embedded_signatures
    if not sigs:
        return None
    br = sigs[0].byte_range
    return data[: br[2] + br[3]]
