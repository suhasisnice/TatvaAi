"""Demo: edit one audit row directly in the database to show the hash chain
catching it. Undo with --restore.

Run from backend/:
    .venv/Scripts/python scripts/tamper_audit_demo.py
    .venv/Scripts/python scripts/tamper_audit_demo.py --restore
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.db import SessionLocal  # noqa: E402
from app.models import AuditLog  # noqa: E402
from app.services.audit import verify_chain  # noqa: E402

BACKUP = Path(__file__).resolve().parent / ".tamper_backup.json"


def main():
    db = SessionLocal()
    try:
        if "--restore" in sys.argv:
            if not BACKUP.exists():
                print("Nothing to restore.")
                return
            saved = json.loads(BACKUP.read_text())
            row = db.query(AuditLog).filter(AuditLog.seq == saved["seq"]).first()
            row.actor = saved["actor"]
            db.commit()
            BACKUP.unlink()
            print("Restored entry", saved["seq"], "->", verify_chain(db))
            return

        rows = db.query(AuditLog).order_by(AuditLog.seq.asc()).all()
        if len(rows) < 3:
            print("Need at least 3 audit entries; run the app or seed first.")
            return
        row = rows[len(rows) // 2]
        BACKUP.write_text(json.dumps({"seq": row.seq, "actor": row.actor}))
        row.actor = "attacker@evil.test"
        db.commit()
        print(f"Tampered with entry {row.seq}.", verify_chain(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
