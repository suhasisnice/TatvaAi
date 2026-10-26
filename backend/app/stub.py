"""Fixed demo data for the stub API (institutions A, B, C). Replace router by router with real services."""
from datetime import datetime

from .schemas import (AlertOut, ApplicationOut, AuditEntry, DocumentOut, Engine, Evidence, Flag, Risk,
                      RiskReason, RuleOutcome, RuleResult, Severity, Tier, User, Verification,
                      VerificationStatus)

PASSWORD = "Pramaan@2026"
NOW = datetime(2026, 10, 26, 12, 0)
RPV = "APH-2024-27-v1"

USERS = {
    "inst-a@pramaan.test": User(id=1, email="inst-a@pramaan.test", name="Aurora Institute (Synthetic)", role="institution", institution_id=1),
    "inst-b@pramaan.test": User(id=2, email="inst-b@pramaan.test", name="Bhavani College (Synthetic)", role="institution", institution_id=2),
    "inst-c@pramaan.test": User(id=3, email="inst-c@pramaan.test", name="Chandra Campus (Synthetic)", role="institution", institution_id=3),
    "officer@pramaan.test": User(id=4, email="officer@pramaan.test", name="Scrutiny Officer", role="officer"),
    "inspector@pramaan.test": User(id=5, email="inspector@pramaan.test", name="EVC Inspector", role="inspector"),
    "admin@pramaan.test": User(id=6, email="admin@pramaan.test", name="Bureau Admin", role="admin"),
}

APPS = [
    ApplicationOut(id=1, institution_id=1, institution_name="Aurora Institute of Technology (Synthetic)", academic_year="2027-28",
                   category="EOA", status="SUBMITTED", open_flags=2,
                   risk=Risk(score=0, tier=Tier.GREEN, reasons=[], rule_pack_version=RPV)),
    ApplicationOut(id=2, institution_id=2, institution_name="Bhavani College of Engineering (Synthetic)", academic_year="2027-28",
                   category="EOA", status="SUBMITTED", open_flags=2,
                   risk=Risk(score=30, tier=Tier.AMBER, rule_pack_version=RPV, reasons=[
                       RiskReason(flag_code="DOC_EXPIRES_BEFORE_AY", contribution=15),
                       RiskReason(flag_code="PROVISIONAL_OC_LIMIT_EXCEEDED", contribution=15)])),
    ApplicationOut(id=3, institution_id=3, institution_name="Chandra Technical Campus (Synthetic)", academic_year="2027-28",
                   category="EOA", status="SUBMITTED", open_flags=14,
                   risk=Risk(score=245.05, tier=Tier.RED, rule_pack_version=RPV, reasons=[
                       RiskReason(flag_code="MODIFIED_AFTER_SIGNING", contribution=40),
                       RiskReason(flag_code="QR_MISMATCH", contribution=40),
                       RiskReason(flag_code="DUPLICATE_FACULTY_CROSS_INSTITUTION", contribution=40),
                       RiskReason(flag_code="TAMPER_SUSPECTED", contribution=13.5, forensic=True)])),
]

FLAGS: dict[int, list[Flag]] = {
    1: [Flag(id=1, code="ISSUER_UNAVAILABLE", engine=Engine.issuer, severity=Severity.INFO, confidence=1,
             message="Karnataka fire portal did not respond (MOCK)", explanation="Routed to manual review.",
             evidence=[Evidence(kind="system", system="MOCK Karnataka fire portal")])],
    2: [Flag(id=2, code="DOC_EXPIRES_BEFORE_AY", engine=Engine.completeness, severity=Severity.MAJOR, confidence=1,
             message="Fire certificate expires before the academic year starts", explanation="Valid till 2027-06-30; year starts 2027-08-01.",
             evidence=[Evidence(kind="document", document_id=3, page=1, bbox=(0.2, 0.4, 0.6, 0.45))],
             rule_id="EXP-FIRE-AY", rule_pack_version=RPV, citation="APH Annexure-2, 2.1, p.81")],
    3: [Flag(id=3, code="MODIFIED_AFTER_SIGNING", engine=Engine.authenticity, severity=Severity.CRITICAL, confidence=0.99,
             message="Land record was changed after it was signed", explanation="Survey number differs from the signed revision.",
             evidence=[Evidence(kind="document", document_id=5, page=1, bbox=(0.3, 0.5, 0.7, 0.55), note="survey_no")])],
}

DOCS = [
    DocumentOut(id=5, application_id=3, type="LAND_DOCUMENT", classification_confidence=0.95, file_name="land_record.pdf",
                sha256="0" * 64, pages=1, signature_status="SIGNED_MODIFIED", proof_level="NONE"),
    DocumentOut(id=3, application_id=2, type="FIRE_SAFETY_CERTIFICATE", classification_confidence=0.97, file_name="fire.pdf",
                sha256="1" * 64, pages=1, signature_status="SIGNED_VALID", proof_level="ISSUER_CONFIRMED"),
]

VERIFS = [Verification(id=1, document_id=3, adapter="state_fire", status=VerificationStatus.VERIFIED, source="MOCK Karnataka fire portal",
                       summary="Certificate found, valid till 2027-06-30", checked_at=NOW)]

RULE_RESULTS = [RuleResult(rule_id="FAC-UG-ENGG-RATIO", title="Faculty-student ratio, UG Engineering (1:20)", outcome=RuleOutcome.FAIL,
                           values={"required": 45, "valid_full_time_faculty": 33}, citation="APH Annexure-5, 5.2, p.95", rule_pack_version=RPV)]

ALERTS = [AlertOut(id=1, kind="ANOMALY", message="Suspected anomaly: land record changed after signing", application_id=3)]

AUDIT = [AuditEntry(seq=1, at=NOW, actor="system", action="seed", entity="stub", payload_hash="0" * 64, prev_hash="0" * 64, hash="1" * 64)]
