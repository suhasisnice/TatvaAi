from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Application, Institution, User


def get_app(db: Session, user: User, app_id: int) -> Application:
    """Institutions only ever see their own applications (404, not 403, so existence is not leaked)."""
    a = db.get(Application, app_id)
    if not a or (user.role == "institution" and a.institution_id != user.institution_id):
        raise HTTPException(404, "Application not found")
    return a


def inst_of(db: Session, app: Application) -> Institution:
    return db.get(Institution, app.institution_id)
