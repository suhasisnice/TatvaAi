from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Institution, User

DEMO_PASSWORD = "Pramaan@2026"  # synthetic demo accounts only
INSTITUTIONS = [
    ("a", "Aurora Institute of Technology (Synthetic)", "Karnataka"),
    ("b", "Bhavani College of Engineering (Synthetic)", "Maharashtra"),
    ("c", "Chandra Technical Campus (Synthetic)", "Tamil Nadu"),
]
STAFF = [("officer", "Demo Officer"), ("inspector", "Demo Inspector")]


def seed_users(db: Session) -> list[tuple[str, str, str]]:
    """Idempotent. Returns (role, email, password) rows for printing."""
    rows = []
    for key, name, state in INSTITUTIONS:
        inst = db.scalar(select(Institution).where(Institution.slug == f"inst-{key}"))
        if not inst:
            inst = Institution(name=name, slug=f"inst-{key}", state=state, aicte_id=f"SYN-AICTE-{1001 + 'abc'.index(key)}")
            db.add(inst)
            db.flush()
        rows.append(("institution", f"inst-{key}@pramaan.test", inst.id, name))
    for role, name in STAFF:
        rows.append((role, f"{role}@pramaan.test", None, name))
    out = []
    for role, email, inst_id, name in rows:
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, name=name, role=role, institution_id=inst_id, password_hash=hash_password(DEMO_PASSWORD)))
        out.append((role, email, DEMO_PASSWORD))
    db.commit()
    return out
