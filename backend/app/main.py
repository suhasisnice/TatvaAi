from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import alerts, applications, audit, auth, documents, mfa, precheck, risk, rules, verification
from app.core.config import settings

app = FastAPI(title="PramaanAI", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.cors_origin], allow_methods=["*"], allow_headers=["*"])

api = APIRouter(prefix="/api/v1")
for m in (auth, mfa, applications, documents, precheck, verification, rules, risk, alerts, audit):
    api.include_router(m.router)
app.include_router(api)


@app.get("/health")
def health():
    return {"status": "ok"}
