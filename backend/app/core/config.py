import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'tatva.db'}")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-tatvaai")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 120

ACADEMIC_YEAR_START = "2027-08-01"
SUBMISSION_DEADLINE = "2027-03-31"

MAX_UPLOAD_MB = 20
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".csv"}
