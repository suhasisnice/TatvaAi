"""All MOCK external systems on one port (9000). Every response says "mock": true.
Data comes from data/synthetic/mock_db.json (python scripts/generate_synthetic.py). Backend adapters read this URL from env."""
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

DB_PATH = Path(os.getenv("MOCK_DB", Path(__file__).resolve().parents[1] / "data" / "synthetic" / "mock_db.json"))
SOURCES = {"estamp", "fire", "occupancy", "digilocker", "udin", "aicte", "faculty_registry", "websites", "footprints", "naac"}

app = FastAPI(title="PramaanAI mock issuers (ALL MOCK)")


def db() -> dict:
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {"mock": True, "db": DB_PATH.exists()}


@app.get("/{source}/{key:path}")
def lookup(source: str, key: str, state: str = "") -> dict:
    if source not in SOURCES:
        raise HTTPException(404, {"mock": True, "error": "unknown source"})
    data = db()
    if f"{source}:{state}" in data["unavailable"]:
        raise HTTPException(503, {"mock": True, "source": source, "error": "source unavailable"})
    record = data[source].get(key)
    return {"mock": True, "source": source, "status": "FOUND" if record is not None else "NOT_FOUND", "record": record}
