"""CONTRACT 4: the Flag and Fact shapes. Every engine returns Flags, every screen shows them.
Changing this file is a `contract:` commit and needs both people to agree."""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    institution = "institution"
    officer = "officer"
    inspector = "inspector"
    admin = "admin"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class Engine(str, Enum):
    issuer = "issuer"
    authenticity = "authenticity"
    completeness = "completeness"
    consistency = "consistency"
    compliance = "compliance"
    infrastructure = "infrastructure"


class Tier(str, Enum):
    GREEN = "GREEN"  # no risk
    AMBER = "AMBER"  # medium risk
    RED = "RED"  # high risk


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    MISMATCH_DETECTED = "MISMATCH_DETECTED"
    EXPIRED = "EXPIRED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SignatureStatus(str, Enum):
    UNSIGNED = "UNSIGNED"
    SIGNED_VALID = "SIGNED_VALID"
    SIGNED_MODIFIED = "SIGNED_MODIFIED"
    SIGNED_INVALID = "SIGNED_INVALID"
    SIGNED_UNTRUSTED = "SIGNED_UNTRUSTED"


class Evidence(BaseModel):
    """Points at proof. Exactly one of document/system is set."""
    kind: Literal["document", "system", "form", "derived"]
    document_id: int | None = None
    page: int | None = None
    # normalised 0-1 box [x0, y0, x1, y1] so the viewer can draw it at any zoom
    bbox: tuple[float, float, float, float] | None = None
    system: str | None = None  # e.g. "MOCK fire portal"
    record_id: str | None = None
    note: str | None = None


class Flag(BaseModel):
    code: str  # e.g. MODIFIED_AFTER_SIGNING (see BUILD_GUIDE / guide Appendix D)
    engine: Engine
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    message: str  # plain language
    explanation: str  # forensic flags start with "Preliminary indicator - requires human verification"
    evidence: list[Evidence] = []
    forensic: bool = False
    # rule-based flags only
    rule_id: str | None = None
    rule_pack_version: str | None = None
    citation: str | None = None  # "APH Annexure-2, 2.1, p.81"
    # set by the API, not by engines
    id: int | None = None
    status: Literal["OPEN", "ACCEPTED", "DISMISSED"] = "OPEN"
    fingerprint: str | None = None  # stable id so re-runs keep officer decisions


class Fact(BaseModel):
    """One node of the evidence graph."""
    subject: str  # "institution", "faculty", "building:Block A", "doc:LAND_DOCUMENT#1"
    attribute: str
    value: str | float | int | bool | None
    unit: str | None = None
    source: Evidence  # provenance


class Verification(BaseModel):
    id: int | None = None
    document_id: int | None = None
    adapter: str
    status: VerificationStatus
    source: str  # always labelled MOCK in the prototype
    summary: str
    checked_at: datetime
    request_hash: str | None = None
    response_hash: str | None = None
    carried_forward_from: str | None = None  # "2026-27"
    manual_note: str | None = None


class RuleResult(BaseModel):
    rule_id: str
    title: str
    outcome: RuleOutcome
    values: dict[str, float | int | str | None] = {}
    citation: str
    rule_pack_version: str


class RiskReason(BaseModel):
    flag_code: str
    contribution: float
    forensic: bool = False


class Risk(BaseModel):
    score: float
    tier: Tier
    reasons: list[RiskReason]
    rule_pack_version: str


class User(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    institution_id: int | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class LoginIn(BaseModel):
    email: str
    password: str


class ApplicationIn(BaseModel):
    academic_year: str  # "2027-28"
    category: Literal["EOA", "INCREASE_INTAKE", "NAME_CHANGE"] = "EOA"


class DocumentOut(BaseModel):
    id: int
    application_id: int
    type: str  # FIRE_SAFETY_CERTIFICATE, UNKNOWN, ...
    classification_confidence: float
    file_name: str
    sha256: str
    pages: int
    signature_status: SignatureStatus
    proof_level: str | None = None


class ApplicationOut(BaseModel):
    id: int
    institution_id: int
    institution_name: str
    academic_year: str
    category: str
    status: Literal["DRAFT", "SUBMITTED", "REOPENED"]
    risk: Risk | None = None
    open_flags: int = 0


class AlertOut(BaseModel):
    id: int
    kind: Literal["MISSING_INFO", "ANOMALY", "DOC_EXPIRING", "DOC_EXPIRED", "PENDING_VERIFICATION"]
    message: str
    application_id: int | None = None
    read: bool = False


class AuditEntry(BaseModel):
    seq: int
    at: datetime
    actor: str
    action: str
    entity: str
    payload_hash: str
    prev_hash: str
    hash: str


class DecisionIn(BaseModel):
    decision: Literal["ACCEPT", "DISMISS"]
    reason: str = Field(min_length=3)  # no decision without a written reason
