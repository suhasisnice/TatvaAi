"""CONTRACT 3: the 10 routers under /api/v1. Stub bodies only; swap in real services one at a time."""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile

from . import stub
from .schemas import (AlertOut, ApplicationIn, ApplicationOut, AuditEntry, DecisionIn, DocumentOut, Flag, LoginIn, Role,
                      RuleResult, Token, User, Verification)

BANNER = "Decision support only. Final decisions rest with competent AICTE authorities."


def current_user(authorization: Annotated[str | None, Header()] = None) -> User:
    email = (authorization or "").removeprefix("Bearer stub-")
    if email not in stub.USERS:
        raise HTTPException(401, "Not signed in")
    return stub.USERS[email]


def staff(user: User = Depends(current_user)) -> User:
    if user.role == Role.institution:
        raise HTTPException(403, "Staff only")
    return user


def admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(403, "Admin only")
    return user


def _app(app_id: int, user: User) -> ApplicationOut:
    a = next((a for a in stub.APPS if a.id == app_id), None)
    if not a or (user.role == Role.institution and a.institution_id != user.institution_id):
        raise HTTPException(404, "Application not found")  # institutions only ever see their own
    return a


auth = APIRouter(prefix="/auth", tags=["auth"])
mfa = APIRouter(prefix="/mfa", tags=["mfa"])
applications = APIRouter(tags=["applications"])
documents = APIRouter(tags=["documents"])
precheck = APIRouter(tags=["precheck"])
verification = APIRouter(tags=["verification"])
rules = APIRouter(tags=["rules"])
risk = APIRouter(tags=["risk"])
alerts = APIRouter(tags=["alerts"])
audit = APIRouter(prefix="/audit", tags=["audit"])
ROUTERS = [auth, mfa, applications, documents, precheck, verification, rules, risk, alerts, audit]


@auth.post("/login")
def login(body: LoginIn) -> Token:
    user = stub.USERS.get(body.email)
    if not user or body.password != stub.PASSWORD:
        raise HTTPException(401, "Wrong email or password")
    return Token(access_token=f"stub-{user.email}", user=user)


@auth.get("/me")
def me(user: User = Depends(current_user)) -> User:
    return user


@mfa.post("/setup")
def mfa_setup(user: User = Depends(staff)) -> dict:
    return {"secret": "STUBSECRET", "mock": True}


@mfa.post("/verify")
def mfa_verify(code: str, user: User = Depends(staff)) -> dict:
    return {"enabled": code == "000000"}


@applications.get("/applications")
def list_applications(user: User = Depends(current_user)) -> list[ApplicationOut]:
    mine = [a for a in stub.APPS if user.role != Role.institution or a.institution_id == user.institution_id]
    return sorted(mine, key=lambda a: -(a.risk.score if a.risk else 0))  # RED first


@applications.post("/applications")
def create_application(body: ApplicationIn, user: User = Depends(current_user)) -> ApplicationOut:
    return ApplicationOut(id=99, institution_id=user.institution_id or 0, institution_name=user.name,
                          academic_year=body.academic_year, category=body.category, status="DRAFT")


@applications.get("/applications/{app_id}")
def get_application(app_id: int, user: User = Depends(current_user)) -> ApplicationOut:
    return _app(app_id, user)


@applications.post("/applications/{app_id}/submit")
def submit(app_id: int, user: User = Depends(current_user)) -> ApplicationOut:
    return _app(app_id, user).model_copy(update={"status": "SUBMITTED"})


@applications.post("/applications/{app_id}/reopen")
def reopen(app_id: int, user: User = Depends(admin)) -> ApplicationOut:
    return _app(app_id, user).model_copy(update={"status": "REOPENED"})


@applications.get("/applications/{app_id}/evidence-graph")
def evidence_graph(app_id: int, user: User = Depends(staff)) -> list[dict]:
    _app(app_id, user)
    return []  # list[Fact] once the graph exists


@documents.get("/applications/{app_id}/documents")
def list_documents(app_id: int, user: User = Depends(current_user)) -> list[DocumentOut]:
    _app(app_id, user)
    return [d for d in stub.DOCS if d.application_id == app_id]


@documents.post("/applications/{app_id}/documents")
def upload_document(app_id: int, file: UploadFile, user: User = Depends(current_user)) -> DocumentOut:
    _app(app_id, user)
    return DocumentOut(id=100, application_id=app_id, type="UNKNOWN", classification_confidence=0.0,
                       file_name=file.filename or "upload", sha256="0" * 64, pages=1, signature_status="UNSIGNED")


@precheck.post("/applications/{app_id}/precheck")
def run_precheck(app_id: int, user: User = Depends(current_user)) -> dict:
    _app(app_id, user)
    return {"must_fix": [], "should_fix": [], "minor": [], "waiting_for_officer": 0}


@verification.get("/applications/{app_id}/verifications")
def list_verifications(app_id: int, user: User = Depends(staff)) -> list[Verification]:
    _app(app_id, user)
    return stub.VERIFS


@verification.post("/verifications/{ver_id}/manual")
def manual_confirmation(ver_id: int, note: str, user: User = Depends(staff)) -> Verification:
    return stub.VERIFS[0].model_copy(update={"manual_note": note})


@rules.get("/rules/packs")
def list_packs(user: User = Depends(staff)) -> list[dict]:
    return [{"version": "v1", "pack": "APH-2024-27", "status": "active", "rules": 2}]


@rules.get("/applications/{app_id}/rule-results")
def rule_results(app_id: int, user: User = Depends(staff)) -> list[RuleResult]:
    _app(app_id, user)
    return stub.RULE_RESULTS


@risk.get("/applications/{app_id}/flags")
def list_flags(app_id: int, user: User = Depends(staff)) -> list[Flag]:
    _app(app_id, user)
    return stub.FLAGS.get(app_id, [])


@risk.post("/flags/{flag_id}/decision")
def decide(flag_id: int, body: DecisionIn, user: User = Depends(staff)) -> dict:
    return {"flag_id": flag_id, "decision": body.decision, "reason": body.reason, "officer": user.email}


@risk.post("/applications/{app_id}/revalidate")
def revalidate(app_id: int, user: User = Depends(staff)) -> ApplicationOut:
    return _app(app_id, user)


@risk.get("/inspections")
def inspections(user: User = Depends(staff)) -> list[dict]:
    return [{"application_id": a.id, "institution": a.institution_name, "score": a.risk.score,
             "why": [r.flag_code for r in a.risk.reasons]} for a in stub.APPS if a.risk and a.risk.tier == "RED"]


@alerts.get("/alerts")
def list_alerts(user: User = Depends(current_user)) -> list[AlertOut]:
    return stub.ALERTS


@alerts.post("/alerts/{alert_id}/read")
def read_alert(alert_id: int, user: User = Depends(current_user)) -> dict:
    return {"id": alert_id, "read": True}


@audit.get("")
def list_audit(user: User = Depends(admin)) -> list[AuditEntry]:
    return stub.AUDIT


@audit.get("/verify")
def verify_chain(user: User = Depends(admin)) -> dict:
    return {"intact": True, "entries": len(stub.AUDIT), "head_hash": stub.AUDIT[-1].hash}
