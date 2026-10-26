from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import BANNER, ROUTERS

app = FastAPI(title="PramaanAI", version="0.1.0", description=BANNER)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
for r in ROUTERS:
    app.include_router(r, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "stub": True, "banner": BANNER}
