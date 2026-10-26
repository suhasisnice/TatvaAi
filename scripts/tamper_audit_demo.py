"""Live-demo helper: edits one audit-log row directly in the database (bypassing the app), then verifies the chain.

Usage: python scripts/tamper_audit_demo.py [--seq N] [--restore]
  default: tampers with a mid-chain entry and prints 'Broken at entry N'. The officer Audit log page then shows the broken banner.
  --restore puts the original payload back (chain intact again)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
import app.models  # noqa: E402,F401
from app.models import AuditLog  # noqa: E402
from app.services.audit import hash_chain  # noqa: E402

BACKUP = ROOT / ".audit_tamper_backup.json"

with SessionLocal() as db:
    if "--restore" in sys.argv:
        b = json.loads(BACKUP.read_text())
        db.get(AuditLog, b["seq"]).payload_json = b["payload_json"]
        db.commit()
        BACKUP.unlink()
        print("restored entry", b["seq"], "->", hash_chain.verify(db))
        sys.exit(0)
    print("before:", hash_chain.verify(db))
    rows = db.scalars(select(AuditLog).order_by(AuditLog.seq)).all()
    if not rows:
        sys.exit("audit log is empty - run scripts/seed.py first")
    seq = int(sys.argv[sys.argv.index("--seq") + 1]) if "--seq" in sys.argv else rows[len(rows) // 2].seq
    row = db.get(AuditLog, seq)
    BACKUP.write_text(json.dumps({"seq": seq, "payload_json": row.payload_json}))
    row.payload_json = row.payload_json[:-1] + ',"tampered":true}' if row.payload_json.endswith("}") else row.payload_json + " "
    db.commit()
    print(f"modified entry {seq} ({row.action} on {row.entity}) directly in the database")
    res = hash_chain.verify(db)
    print("after: ", res)
    print(f"RESULT: {'Chain intact' if res['intact'] else 'Broken at entry ' + str(res['broken_at'])}")
