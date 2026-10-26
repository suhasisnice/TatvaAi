"""Shared plumbing for the five engines: run context, evidence index, flag construction."""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Document, ExtractedField

SEV_RANK = {"INFO": 0, "MINOR": 1, "MAJOR": 2, "CRITICAL": 3}
FORENSIC_LABEL = "Preliminary indicator — requires human verification"
VERIFICATION_STATUSES = ("VERIFIED", "MISMATCH_DETECTED", "EXPIRED", "VERIFICATION_PENDING", "SOURCE_UNAVAILABLE", "MANUAL_REVIEW_REQUIRED")


class Evidence:
    """Index of extracted fields so any flag can point at document + page + bounding box."""

    def __init__(self, db: Session, app: Application):
        self.docs: list[Document] = list(db.scalars(select(Document).where(Document.application_id == app.id).order_by(Document.id)))
        self.by_id = {d.id: d for d in self.docs}
        self._fields = {(f.document_id, f.name): f for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id.in_(list(self.by_id) or [0])))}

    def of_type(self, dtype: str) -> list[Document]:
        return [d for d in self.docs if d.doc_type == dtype]

    def value(self, doc_id: int, name: str):
        f = self._fields.get((doc_id, name))
        return f.value if f else None

    def field(self, doc_id: int, name: str) -> dict:
        f = self._fields.get((doc_id, name))
        if not f or f.x0 is None:
            return {"document_id": doc_id, "page": 1, "bbox": None, "field": name, **({"value": f.value} if f else {})}
        return {"document_id": doc_id, "page": f.page, "bbox": [f.x0, f.y0, f.x1, f.y1], "field": name, "value": f.value}

    def doc(self, doc_id: int) -> dict:
        return {"document_id": doc_id, "page": 1, "bbox": None}


@dataclass
class Run:
    db: Session
    app: Application
    pack: dict
    version: str
    ctx: dict
    results: list[dict]
    ev: Evidence
    rules: dict = field(default_factory=dict)  # rule id -> rule
    verifs: list[dict] = field(default_factory=list)  # filled by the issuer engine
    today: date = field(default_factory=date.today)

    @property
    def thresholds(self) -> dict:
        return self.pack.get("risk", {}).get("thresholds", {})


def form_source(r: Run, record: str) -> dict:
    return {"system_source": "Online application form", "record_id": record, "application_id": r.app.id}


def make_flag(engine: str, code: str, severity: str, message: str, evidence: list, *, explanation: str = "", confidence: float = 1.0,
              rule: dict | None = None, rule_version: str | None = None, document_id: int | None = None, forensic: bool = False, key: str = "") -> dict:
    if forensic:
        explanation = f"{FORENSIC_LABEL}. {explanation}".strip()
    return dict(engine=engine, code=code, severity=severity, message=message, explanation=explanation, confidence=confidence, evidence=evidence,
                rule_id=rule["id"] if rule else None, rule_pack_version=rule_version if rule else None, citation=rule["citation"] if rule else None,
                document_id=document_id, forensic=forensic, fingerprint=f"{engine}|{code}|{rule['id'] if rule else ''}|{document_id or ''}|{key}")


def flag_from_result(engine: str, res: dict, r: Run, evidence: list, code: str | None = None, document_id: int | None = None, key: str = "") -> dict:
    rule = r.rules[res["rule_id"]]
    expl = f"{rule['title']}. Rule {rule['id']} ({r.version}), {rule['citation']['source']} {rule['citation']['clause']}, p. {rule['citation']['page']}."
    return make_flag(engine, code or res.get("code") or "RULE_FAILED", res["severity"], res["message"], evidence, explanation=expl, rule=rule,
                     rule_version=r.version, document_id=document_id, key=key or (res.get("scope") or ""))
