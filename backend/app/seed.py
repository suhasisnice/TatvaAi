"""Resets the database and loads three synthetic demo institutions:
Aurora (GREEN), Bhavani (AMBER, left as an editable draft for a live
pre-check + submit demo) and Chandra (RED, submitted).

Run: .venv/Scripts/python -m app.seed
"""
from pathlib import Path

from app.core.db import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models import (
    Institution, User, Application, Document, IssuerRecord, FacultyRegistryEntry,
)
from app.services import extraction, pipeline
from app.services.generate_docs import generate_all, DATA_DIR

DEMO_PASSWORD = "Pramaan@2026"

INSTITUTIONS = [
    dict(slug="aurora", name="Aurora Institute of Technology (Synthetic)", state="Karnataka",
         aicte_id="SYN-AICTE-1001", trust_name="Aurora Vidya Trust", survey_no="SY-42/3A",
         declared_faculty=26, declared_built_up_m2=6100, footprint_estimate_m2=6000,
         approved_intake=480, website_faculty_count=26),
    dict(slug="bhavani", name="Bhavani College of Engineering (Synthetic)", state="Maharashtra",
         aicte_id="SYN-AICTE-1002", trust_name="Bhavani Shiksha Samiti", survey_no="SY-77/1",
         declared_faculty=42, declared_built_up_m2=10100, footprint_estimate_m2=10000,
         approved_intake=720, website_faculty_count=42),
    dict(slug="chandra", name="Chandra Technical Campus (Synthetic)", state="Tamil Nadu",
         aicte_id="SYN-AICTE-1003", trust_name="Chandra Educational Society", survey_no="SY-118/4B",
         declared_faculty=109, declared_built_up_m2=31500, footprint_estimate_m2=24100,
         approved_intake=2400, website_faculty_count=85),
]

DOC_FILES = {
    "aurora": ["affidavit_2.pdf", "ter_receipt.pdf", "occupancy_certificate.pdf",
               "fire_safety_certificate.pdf", "satellite_map.pdf", "audited_accounts.pdf",
               "faculty_list.csv", "lab_photo.jpg"],
    "bhavani": ["affidavit_2.pdf", "ter_receipt.pdf", "occupancy_certificate.pdf",
                "fire_safety_certificate.pdf", "satellite_map.pdf", "audited_accounts.pdf",
                "faculty_list.csv", "lab_photo.jpg"],
    "chandra": ["affidavit_2.pdf", "ter_receipt.pdf", "occupancy_certificate.pdf",
                "fire_safety_certificate.pdf", "satellite_map.pdf", "audited_accounts.pdf",
                "land_document.pdf", "faculty_list.csv", "classroom_photo.jpg", "lab_photo.jpg"],
}

SUBMIT_IMMEDIATELY = {"aurora": True, "bhavani": False, "chandra": True}


def ingest_document(db, app_obj: Application, src: Path, upload_dir: Path):
    dest_dir = upload_dir / str(app_obj.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    dest.write_bytes(src.read_bytes())

    text = extraction.extract_text(dest)
    doc_type, confidence = extraction.classify(src.name, text)
    fields = extraction.extract_fields(text)
    signed, signer = extraction.signature_marker(text)
    fields["_signed"] = signed
    fields["_signer"] = signer
    tampered = [ln for ln in text.splitlines() if ln.strip().lower().startswith("tampered-field:")]
    if tampered:
        fields["_tampered_field"] = tampered[0].split(":", 1)[1].strip()

    if doc_type == "FACULTY_LIST":
        import csv as csv_mod
        fields["_signed"] = True
        with open(dest, newline="", encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        ids = [r["faculty_id"] for r in rows if r.get("faculty_id")]
        dup_rows = (
            db.query(FacultyRegistryEntry)
            .filter(FacultyRegistryEntry.faculty_id.in_(ids),
                     FacultyRegistryEntry.institution_slug != app_obj.institution.slug)
            .all()
        )
        fields["_duplicate_faculty_ids"] = sorted({r.faculty_id for r in dup_rows})

    doc = Document(
        application_id=app_obj.id, doc_type=doc_type, file_name=src.name, storage_path=str(dest),
        sha256=extraction.sha256_file(dest), classification_confidence=confidence,
        signed=signed, extracted_fields=fields,
    )
    db.add(doc)
    db.commit()
    return doc


def main():
    from app.core.config import UPLOAD_DIR

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    generate_all()

    db = SessionLocal()

    institutions = {}
    for data in INSTITUTIONS:
        inst = Institution(**data)
        db.add(inst)
        db.flush()
        institutions[data["slug"]] = inst
    db.commit()

    users = [
        ("inst-aurora@pramaan.test", "Aurora Admin", "institution", "aurora"),
        ("inst-bhavani@pramaan.test", "Bhavani Admin", "institution", "bhavani"),
        ("inst-chandra@pramaan.test", "Chandra Admin", "institution", "chandra"),
        ("officer@pramaan.test", "Regulation Bureau Officer", "officer", None),
        ("inspector@pramaan.test", "EVC Inspector", "inspector", None),
        ("admin@pramaan.test", "Regulation Bureau Admin", "admin", None),
    ]
    for email, name, role, slug in users:
        db.add(User(
            email=email, name=name, role=role, password_hash=hash_password(DEMO_PASSWORD),
            institution_id=institutions[slug].id if slug else None,
        ))
    db.commit()

    # Mock AICTE faculty registry: 12 faculty genuinely registered at "Delta
    # Polytechnic (Synthetic)" (not a demo institution of its own) that
    # Chandra's roster also lists as its own full-time staff.
    for i in range(1, 13):
        db.add(FacultyRegistryEntry(faculty_id=f"DEL-F{i:03d}", institution_slug="delta", name=f"Faculty D{i}"))
    db.commit()

    # Mock issuer records
    db.add(IssuerRecord(institution_slug="aurora", doc_type="FIRE_SAFETY_CERTIFICATE",
                         source_name="Karnataka Fire NOC Portal (MOCK)", available=False))
    original_land = DATA_DIR / "chandra" / "land_document_original.pdf"
    db.add(IssuerRecord(institution_slug="chandra", doc_type="LAND_DOCUMENT",
                         source_name="DigiLocker (MOCK)", available=True,
                         expected_fields={"survey_no": "SY-118/4B"},
                         registered_sha256=extraction.sha256_file(original_land)))
    db.commit()

    # Applications + documents
    for slug, inst in institutions.items():
        app_obj = Application(institution_id=inst.id, category="EOA", academic_year="2027-28", status="DRAFT")
        db.add(app_obj)
        db.commit()
        db.refresh(app_obj)

        for fname in DOC_FILES[slug]:
            src = DATA_DIR / slug / fname
            ingest_document(db, app_obj, src, UPLOAD_DIR)

        pipeline.run_pipeline(db, app_obj, actor="seed")

        if SUBMIT_IMMEDIATELY[slug]:
            from datetime import datetime
            app_obj.status = "SUBMITTED"
            app_obj.submitted_at = datetime.utcnow()
            db.commit()

    db.close()
    print("Seed complete. Demo users (password Pramaan@2026):")
    for email, name, role, slug in users:
        print(f"  {role:10s} {email}")


if __name__ == "__main__":
    main()
