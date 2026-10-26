"""Real PDF digital-signature validation (pyHanko).

Status per document:
  UNSIGNED          no signature
  SIGNED_VALID      signature valid, trusted by the test root CA, nothing changed after signing
  SIGNED_MODIFIED   signature valid and trusted, but the file was changed after it was signed
                    (an incremental update); `changed_fields` names what changed
  SIGNED_UNTRUSTED  signature is mathematically valid but the signer does not chain to our root
  SIGNED_INVALID    the signed bytes were altered or the signature does not verify
"""
import io
import logging
from pathlib import Path

from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
from pypdf import PdfReader

from app.services import pki

# pyHanko logs a stack trace whenever diff analysis finds a post-signing edit; we report that as a flag instead.
for _name in ("pyhanko.sign.diff_analysis", "pyhanko.sign.validation", "pyhanko_certvalidator"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)


def _fields_from_bytes(data: bytes) -> dict:
    from app.services.extraction import extract_fields
    try:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return {}
    return extract_fields(text)


def inspect(path: Path) -> dict:
    """Returns {"status", "signer", "changed_fields": [{"field", "was", "now"}]}."""
    if path.suffix.lower() != ".pdf":
        return {"status": "UNSIGNED", "signer": None, "changed_fields": []}
    data = path.read_bytes()
    try:
        reader = PdfFileReader(io.BytesIO(data))
        sigs = reader.embedded_signatures
    except Exception:
        return {"status": "UNSIGNED", "signer": None, "changed_fields": []}
    if not sigs:
        return {"status": "UNSIGNED", "signer": None, "changed_fields": []}

    sig = sigs[0]
    signer = None
    try:
        signer = sig.signer_cert.subject.native.get("common_name")
    except Exception:
        pass

    pki.ensure_root()
    vc = ValidationContext(trust_roots=[load_cert_from_pemder(str(pki.ROOT_CERT))], allow_fetching=False)
    try:
        status = validate_pdf_signature(sig, vc)
    except Exception:
        return {"status": "SIGNED_INVALID", "signer": signer, "changed_fields": []}

    if not (status.intact and status.valid):
        return {"status": "SIGNED_INVALID", "signer": signer, "changed_fields": []}
    if not status.trusted:
        return {"status": "SIGNED_UNTRUSTED", "signer": signer, "changed_fields": []}
    if status.bottom_line:
        return {"status": "SIGNED_VALID", "signer": signer, "changed_fields": []}

    # Valid + trusted but modified afterwards: cut the file back to the signed revision and diff the fields.
    br = sig.byte_range
    signed_fields = _fields_from_bytes(data[: br[2] + br[3]])
    current_fields = _fields_from_bytes(data)
    changed = [
        {"field": k, "was": signed_fields.get(k), "now": current_fields.get(k)}
        for k in sorted(set(signed_fields) | set(current_fields))
        if signed_fields.get(k) != current_fields.get(k) and k != "tampered_field"
    ]
    return {"status": "SIGNED_MODIFIED", "signer": signer, "changed_fields": changed}
