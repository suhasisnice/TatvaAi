"""MOCK external systems (SHCIL, DigiLocker, ICAI UDIN, accreditation lists, state portals, AICTE records, geo data).
Every JSON response carries mock=true. Data comes from the synthetic generator's mock_db.json (reloaded when it changes)."""
import html
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

DB_PATH = Path(os.environ.get("MOCK_DB", "/app/data/synthetic/mock_db.json"))
app = FastAPI(title="PramaanAI mock issuers (MOCK)")
_cache = {"mtime": None, "db": {}}


def db() -> dict:
    m = DB_PATH.stat().st_mtime if DB_PATH.exists() else None
    if m != _cache["mtime"]:
        _cache.update(mtime=m, db=json.loads(DB_PATH.read_text()) if m else {})
    return _cache["db"]


def ok(**kw) -> dict:
    return {"mock": True, **kw}


def lookup(section: str, key: str) -> dict:
    rec = db().get(section, {}).get(key)
    if rec is None:
        raise HTTPException(404, detail={"mock": True, "status": "NOT_FOUND", "key": key})
    return ok(status="FOUND", record=rec)


def portal(kind: str, state: str):
    b = db().get("portal_behaviour", {}).get(kind, {}).get(state)
    if b == "NO_API":
        raise HTTPException(501, detail={"mock": True, "status": "NO_API", "message": f"{state} {kind} portal has no API"})
    if isinstance(b, int):
        raise HTTPException(b, detail={"mock": True, "status": "UNAVAILABLE", "message": f"{state} {kind} portal down"})


@app.exception_handler(HTTPException)
async def _h(_, exc: HTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"mock": True, "detail": exc.detail}
    return JSONResponse(body, status_code=exc.status_code)


@app.get("/health")
def health():
    return ok(status="ok")


@app.get("/shcil/verify")
def shcil(cert_no: str):
    return lookup("shcil", cert_no)


@app.get("/digilocker/issued/{uri:path}")
def digilocker(uri: str):
    return lookup("digilocker", uri)


@app.get("/udin/verify")
def udin(udin: str):
    return lookup("udin", udin)


@app.get("/nirf/list")
def nirf():
    return ok(edition="8th", institutions=db()["accreditation"]["nirf"])


@app.get("/nba/accredited")
def nba():
    return ok(institutions=db()["accreditation"]["nba"])


@app.get("/naac/grades")
def naac():
    return ok(grades=db()["accreditation"]["naac"])


@app.get("/fire/{state}/verify")
def fire(state: str, cert_no: str):
    portal("fire", state)
    rec = db().get("fire", {}).get(state, {}).get(cert_no)
    if rec is None:
        raise HTTPException(404, detail={"mock": True, "status": "NOT_FOUND", "key": cert_no})
    return ok(status="FOUND", record=rec)


@app.get("/occupancy/{state}/verify")
def occupancy(state: str, cert_no: str):
    portal("occupancy", state)
    rec = db().get("occupancy", {}).get(state, {}).get(cert_no)
    if rec is None:
        raise HTTPException(404, detail={"mock": True, "status": "NOT_FOUND", "key": cert_no})
    return ok(status="FOUND", record=rec)


@app.get("/aicte/records/{institution_id}")
def aicte_records(institution_id: str):
    return lookup("aicte_records", institution_id)


@app.get("/aicte/faculty-registry/{faculty_id}")
def faculty_registry(faculty_id: str):
    return ok(faculty_id=faculty_id, registrations=db().get("faculty_registry", {}).get(faculty_id, []))


@app.get("/web/{slug}/mandatory-disclosure", response_class=HTMLResponse)
def disclosure(slug: str):
    w = db().get("websites", {}).get(slug)
    if not w:
        raise HTTPException(404, detail={"mock": True, "status": "NOT_FOUND"})
    e = html.escape
    return (f"<html><body><h1>{e(w['name'])} - Mandatory Disclosure (MOCK website)</h1>"
            f"<table id='disclosure'><tr><th>Total sanctioned intake</th><td id='intake'>{w['intake_total']}</td></tr>"
            f"<tr><th>Full-time faculty</th><td id='faculty'>{w['faculty_total']}</td></tr>"
            f"<tr><th>Accreditation</th><td id='accreditation'>{e(w['accreditation'])}</td></tr></table></body></html>")


@app.get("/geo/footprints/{campus_id}")
def footprints(campus_id: str):
    fc = db().get("footprints", {}).get(campus_id)
    if not fc:
        raise HTTPException(404, detail={"mock": True, "status": "NOT_FOUND"})
    return fc
