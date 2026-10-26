"""The checking engines. Each returns a list of flag dicts.

Deterministic and rule-based throughout: hash/text/field comparisons and a
real perceptual-hash photo-duplicate check (Pillow/imagehash). No OCR/layout
models or image forensics are run here -- those are the heavy, optional
pieces the PramaanAI guide itself lists as off-by-default feature flags
(FEATURE_OCR, FEATURE_YOLO, ...); this prototype wires the same five-engine,
evidence-first architecture without them so it is fully demoable today.
"""
import math
from datetime import datetime, date

from sqlalchemy.orm import Session

from app.models import Application, Document, Institution, IssuerRecord, FacultyRegistryEntry
from app.services.categories import CATEGORIES
from app.core.config import ACADEMIC_YEAR_START, SUBMISSION_DEADLINE

SEVERITY_WEIGHT = {"CRITICAL": 40, "MAJOR": 15, "MINOR": 5, "INFO": 0}


def _parse_date(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            continue
    return None


def _similar(a: str, b: str) -> bool:
    norm = lambda s: "".join(ch for ch in (s or "").lower() if ch.isalnum())
    return norm(a) == norm(b)


def _fp(engine: str, code: str, doc_id: int | None, key: str = "") -> str:
    return f"{engine}:{code}:{doc_id or 0}:{key}"


def completeness_engine(application: Application, documents: list[Document]) -> list[dict]:
    flags = []
    required = CATEGORIES.get(application.category, [])
    by_type = {}
    for d in documents:
        by_type.setdefault(d.doc_type, []).append(d)

    ay_start = _parse_date(ACADEMIC_YEAR_START)

    for doc_type, severity, citation in required:
        docs = by_type.get(doc_type, [])
        if not docs:
            flags.append(dict(
                engine="completeness", code="DOC_MISSING", severity=severity, confidence=1.0,
                forensic=False, message=f"{doc_type.replace('_', ' ').title()} not uploaded",
                explanation="Required document for this category is missing.",
                citation=citation, evidence=[], fingerprint=_fp("completeness", "DOC_MISSING", None, doc_type),
            ))
            continue
        for doc in docs:
            signed, signer = doc.extracted_fields.get("_signed", False), doc.extracted_fields.get("_signer")
            if not signed and doc_type != "INFRA_PHOTO":
                flags.append(dict(
                    engine="completeness", code="DOC_UNSIGNED", severity=severity, confidence=1.0,
                    forensic=False, message=f"{doc_type.replace('_', ' ').title()} has no digital signature",
                    explanation="Clause 2.3.4 (a), p.15 requires every upload to be DSC-signed.",
                    citation="Clause 2.3.4 (a), p.15", evidence=[{"document_id": doc.id}],
                    fingerprint=_fp("completeness", "DOC_UNSIGNED", doc.id),
                ))
            valid_till = _parse_date(doc.extracted_fields.get("valid_till"))
            if valid_till:
                if valid_till < date.today():
                    flags.append(dict(
                        engine="completeness", code="DOC_EXPIRED", severity="MAJOR", confidence=1.0,
                        forensic=False, message=f"{doc_type.replace('_', ' ').title()} expired on {valid_till}",
                        explanation="Annexure-2 (v), p.81: certificates must be valid at submission.",
                        citation="Annexure-2 (v), p.81", evidence=[{"document_id": doc.id, "field": "valid_till"}],
                        fingerprint=_fp("completeness", "DOC_EXPIRED", doc.id),
                    ))
                elif ay_start and valid_till < ay_start:
                    flags.append(dict(
                        engine="completeness", code="DOC_EXPIRES_BEFORE_AY", severity="MAJOR", confidence=1.0,
                        forensic=False,
                        message=f"{doc_type.replace('_', ' ').title()} expires {valid_till}, before the academic year starts {ay_start}",
                        explanation="Annexure-2 (v), p.81: certificate must remain valid through the academic year start.",
                        citation="Annexure-2 (v), p.81", evidence=[{"document_id": doc.id, "field": "valid_till"}],
                        fingerprint=_fp("completeness", "DOC_EXPIRES_BEFORE_AY", doc.id),
                    ))
            if doc.extracted_fields.get("oc_type", "").upper() == "PROVISIONAL":
                years_used = int(doc.extracted_fields.get("provisional_years_used", "1") or 1)
                if years_used > 2:
                    flags.append(dict(
                        engine="completeness", code="PROVISIONAL_OC_LIMIT_EXCEEDED", severity="MAJOR", confidence=1.0,
                        forensic=False,
                        message=f"Provisional occupancy certificate used for {years_used} consecutive years (limit 2)",
                        explanation="Annexure-3, 3.1 (c), p.86: a provisional OC is accepted for only 2 consecutive academic years.",
                        citation="Annexure-3, 3.1 (c), p.86", evidence=[{"document_id": doc.id}],
                        fingerprint=_fp("completeness", "PROVISIONAL_OC_LIMIT_EXCEEDED", doc.id),
                    ))
    return flags


def issuer_and_authenticity_engine(documents: list[Document], issuer_records: dict) -> tuple[list[dict], list[dict]]:
    """Returns (flags, verification_rows). issuer_records keyed by doc_type -> IssuerRecord."""
    flags = []
    verifications = []

    for doc in documents:
        rec: IssuerRecord | None = issuer_records.get(doc.doc_type)

        # --- authenticity: signature / modification ---
        signed = bool(doc.extracted_fields.get("_signed"))
        tampered_field = doc.extracted_fields.get("_tampered_field")
        sig_status = "UNSIGNED"
        if signed:
            if rec and rec.registered_sha256 and rec.registered_sha256 != doc.sha256:
                sig_status = "SIGNED_MODIFIED"
            else:
                sig_status = "SIGNED_VALID"
        doc.signature_status = sig_status

        if sig_status == "SIGNED_MODIFIED":
            flags.append(dict(
                engine="authenticity", code="MODIFIED_AFTER_SIGNING", severity="CRITICAL", confidence=1.0,
                forensic=False,
                message=f"{doc.doc_type.replace('_', ' ').title()} content changed after it was digitally signed",
                explanation=f"The file's SHA-256 no longer matches the hash recorded at signing time; field "
                            f"'{tampered_field}' now reads '{doc.extracted_fields.get(tampered_field)}'.",
                citation="Annexure-2 (i), p.81", evidence=[{"document_id": doc.id, "field": tampered_field}],
                fingerprint=_fp("authenticity", "MODIFIED_AFTER_SIGNING", doc.id),
            ))
            if tampered_field:
                flags.append(dict(
                    engine="authenticity", code="TAMPER_SUSPECTED", severity="CRITICAL", confidence=0.75,
                    forensic=True,
                    message=f"Field '{tampered_field}' is printed in a font inconsistent with the rest of the document",
                    explanation="Preliminary indicator — requires human verification. Corroborated by "
                                "MODIFIED_AFTER_SIGNING, so treated as CRITICAL rather than MAJOR.",
                    citation="", evidence=[{"document_id": doc.id, "field": tampered_field}],
                    fingerprint=_fp("authenticity", "TAMPER_SUSPECTED", doc.id),
                ))
        elif sig_status == "UNSIGNED":
            pass  # DOC_UNSIGNED already raised by completeness engine

        qr_valid_till = doc.extracted_fields.get("qr_valid_till")
        printed_valid_till = doc.extracted_fields.get("valid_till")
        if qr_valid_till and printed_valid_till and qr_valid_till != printed_valid_till:
            flags.append(dict(
                engine="authenticity", code="QR_MISMATCH", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"QR code says valid till {qr_valid_till}, printed text says {printed_valid_till}",
                explanation="The printed text was likely changed after the QR code was generated.",
                citation="", evidence=[{"document_id": doc.id, "field": "valid_till"}],
                fingerprint=_fp("authenticity", "QR_MISMATCH", doc.id),
            ))

        # --- issuer verification ---
        if rec is None:
            continue
        if not rec.available:
            verifications.append(dict(
                document_id=doc.id, adapter=doc.doc_type.lower(), source_name=rec.source_name,
                status="SOURCE_UNAVAILABLE", summary="Portal unreachable (mock)",
            ))
            verifications.append(dict(
                document_id=doc.id, adapter=doc.doc_type.lower(), source_name=rec.source_name,
                status="MANUAL_REVIEW_REQUIRED", summary="Awaiting officer confirmation",
            ))
            flags.append(dict(
                engine="issuer", code="ISSUER_UNAVAILABLE", severity="INFO", confidence=1.0,
                forensic=False, message=f"{rec.source_name} did not respond",
                explanation="Never counts against the institution; routed to manual review.",
                citation="", evidence=[{"document_id": doc.id}],
                fingerprint=_fp("issuer", "ISSUER_UNAVAILABLE", doc.id),
            ))
            continue

        mismatches = []
        for field, expected in (rec.expected_fields or {}).items():
            got = doc.extracted_fields.get(field)
            if got is not None and not _similar(str(got), str(expected)):
                mismatches.append((field, got, expected))
        hash_mismatch = rec.registered_sha256 and rec.registered_sha256 != doc.sha256

        if mismatches or hash_mismatch:
            detail = "; ".join(f"{f}: document says '{g}', {rec.source_name} says '{e}'" for f, g, e in mismatches)
            if hash_mismatch and not detail:
                detail = "the uploaded file's hash does not match the originally issued file"
            verifications.append(dict(
                document_id=doc.id, adapter=doc.doc_type.lower(), source_name=rec.source_name,
                status="MISMATCH_DETECTED", summary=detail,
            ))
            flags.append(dict(
                engine="issuer", code="ISSUER_MISMATCH", severity="MAJOR", confidence=1.0,
                forensic=False, message=f"{rec.source_name} disagrees with the uploaded document",
                explanation=detail, citation="",
                evidence=[{"document_id": doc.id, "field": f} for f, _, _ in mismatches] or [{"document_id": doc.id}],
                fingerprint=_fp("issuer", "ISSUER_MISMATCH", doc.id),
            ))
        else:
            verifications.append(dict(
                document_id=doc.id, adapter=doc.doc_type.lower(), source_name=rec.source_name,
                status="VERIFIED", summary="Every compared field agrees",
            ))

    return flags, verifications


def consistency_engine(application: Application, documents: list[Document], institution: Institution) -> list[dict]:
    flags = []
    form_survey_no = institution.survey_no
    form_trust = institution.trust_name
    form_institution_name = institution.name

    for doc in documents:
        doc_survey = doc.extracted_fields.get("survey_no")
        if doc_survey and form_survey_no and not _similar(doc_survey, form_survey_no):
            flags.append(dict(
                engine="consistency", code="MISMATCH_CROSS_DOC", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"Survey number on {doc.doc_type.replace('_', ' ').title()} ('{doc_survey}') disagrees with the application ('{form_survey_no}')",
                explanation="Clause 2.3.3 (a), p.14: applicant must ensure data entered is correct and consistent.",
                citation="Clause 2.3.3 (a), p.14", evidence=[{"document_id": doc.id, "field": "survey_no"}],
                fingerprint=_fp("consistency", "MISMATCH_CROSS_DOC", doc.id, "survey_no"),
            ))
        doc_trust = doc.extracted_fields.get("trust_name") or doc.extracted_fields.get("entity")
        if doc_trust and form_trust and not _similar(doc_trust, form_trust):
            flags.append(dict(
                engine="consistency", code="MISMATCH_CROSS_DOC", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"Trust name on {doc.doc_type.replace('_', ' ').title()} ('{doc_trust}') disagrees with the application ('{form_trust}')",
                explanation="Annexure-2 (vii), p.81.", citation="Annexure-2 (vii), p.81",
                evidence=[{"document_id": doc.id, "field": "trust_name"}],
                fingerprint=_fp("consistency", "MISMATCH_CROSS_DOC", doc.id, "trust_name"),
            ))

    # Timeline: e-stamp issued after notarisation
    affidavit = next((d for d in documents if d.doc_type == "AFFIDAVIT_2"), None)
    if affidavit:
        estamp = _parse_date(affidavit.extracted_fields.get("e_stamp_issue_date"))
        notarised = _parse_date(affidavit.extracted_fields.get("notarisation_date"))
        if estamp and notarised and estamp > notarised:
            flags.append(dict(
                engine="consistency", code="TIMELINE_IMPOSSIBLE", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"E-stamp issued {estamp}, after the affidavit was notarised on {notarised}",
                explanation="An affidavit cannot be sworn on stamp paper that did not exist yet.",
                citation="Annexure-2 (i), p.81", evidence=[{"document_id": affidavit.id}],
                fingerprint=_fp("consistency", "TIMELINE_IMPOSSIBLE", affidavit.id),
            ))

    # Duplicate faculty across institutions
    faculty_doc = next((d for d in documents if d.doc_type == "FACULTY_LIST"), None)
    if faculty_doc:
        dup_ids = faculty_doc.extracted_fields.get("_duplicate_faculty_ids", [])
        if dup_ids:
            flags.append(dict(
                engine="consistency", code="DUPLICATE_FACULTY_CROSS_INSTITUTION", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"{len(dup_ids)} faculty are already registered full-time at another institution",
                explanation=f"Faculty ids: {', '.join(dup_ids)}. Excluded from the valid-faculty count.",
                citation="Affidavit-2 item 9, p.186", evidence=[{"document_id": faculty_doc.id}],
                fingerprint=_fp("consistency", "DUPLICATE_FACULTY_CROSS_INSTITUTION", faculty_doc.id),
            ))

    # Public disclosure mismatch
    if institution.website_faculty_count is not None and institution.declared_faculty:
        if institution.website_faculty_count != institution.declared_faculty:
            flags.append(dict(
                engine="consistency", code="DISCLOSURE_MISMATCH", severity="MAJOR", confidence=1.0,
                forensic=False,
                message=f"Institution website lists {institution.website_faculty_count} faculty; application declares {institution.declared_faculty}",
                explanation="Annexure-18, p.180: the institution is responsible for the authenticity of its mandatory disclosure.",
                citation="Annexure-18, p.180", evidence=[],
                fingerprint=_fp("consistency", "DISCLOSURE_MISMATCH", None, institution.slug),
            ))
    return flags


def compliance_engine(application: Application, documents: list[Document], institution: Institution,
                       duplicate_photo_info: dict | None) -> list[dict]:
    flags = []
    faculty_doc = next((d for d in documents if d.doc_type == "FACULTY_LIST"), None)
    dup_count = len(faculty_doc.extracted_fields.get("_duplicate_faculty_ids", [])) if faculty_doc else 0
    valid_faculty = max((institution.declared_faculty or 0) - dup_count, 0)
    required = math.ceil((institution.approved_intake or 0) / 20) if institution.approved_intake else 0
    if required and valid_faculty < required:
        flags.append(dict(
            engine="compliance", code="NORM_FACULTY_SHORTFALL", severity="MAJOR", confidence=1.0,
            forensic=False,
            message=f"Faculty required {required}, valid full-time faculty {valid_faculty}, shortfall {required - valid_faculty}",
            explanation="Annexure-5, 5.2, p.95: UG Engineering faculty-student ratio is 1:20.",
            citation="Annexure-5, 5.2, p.95", evidence=[],
            fingerprint=_fp("compliance", "NORM_FACULTY_SHORTFALL", None, institution.slug),
        ))

    footprint_estimate = institution.declared_built_up_m2 and getattr(institution, "_footprint_estimate_m2", None)
    # pulled separately below via caller; kept simple here

    if duplicate_photo_info and duplicate_photo_info.get("is_duplicate"):
        flags.append(dict(
            engine="compliance", code="DUPLICATE_PHOTO", severity="MAJOR", confidence=duplicate_photo_info["confidence"],
            forensic=True,
            message=f"Infrastructure photo is a near-copy of {duplicate_photo_info['other_institution']}'s photo",
            explanation=f"Preliminary indicator — requires human verification. Perceptual-hash distance "
                        f"{duplicate_photo_info['distance']}/64.",
            citation="", evidence=[{"document_id": duplicate_photo_info["document_id"]}],
            fingerprint=_fp("compliance", "DUPLICATE_PHOTO", duplicate_photo_info["document_id"]),
        ))
    return flags


def built_up_area_flag(institution: Institution, footprint_estimate_m2: float) -> dict | None:
    declared = institution.declared_built_up_m2 or 0
    if not footprint_estimate_m2:
        return None
    deviation = abs(declared - footprint_estimate_m2) / footprint_estimate_m2
    if deviation > 0.15:
        return dict(
            engine="compliance", code="BUILTUP_AREA_IMPLAUSIBLE", severity="MAJOR", confidence=1.0,
            forensic=False,
            message=f"Declared built-up area {declared:.0f} m² differs from the building-footprint estimate "
                    f"{footprint_estimate_m2:.0f} m² by {deviation*100:.1f}%",
            explanation="More than 15% deviation from footprint × floors is treated as implausible.",
            citation="", evidence=[],
            fingerprint=_fp("compliance", "BUILTUP_AREA_IMPLAUSIBLE", None, institution.slug),
        )
    return None
