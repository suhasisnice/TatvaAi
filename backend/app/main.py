from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.db import Base, engine
from app.routers import auth, applications, risk, audit_router, alerts

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TatvaAI prototype", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(risk.router)
app.include_router(audit_router.router)
app.include_router(alerts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
