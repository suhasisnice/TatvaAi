from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_password, create_access_token
from app.models import User
from app.schemas import LoginIn, TokenOut
from app.deps import get_current_user
from app.services import audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.active:
        raise HTTPException(status_code=403, detail="Account deactivated")
    token = create_access_token(user.email, user.role, user.institution_id)
    audit.record(db, user.email, "auth.login", f"user:{user.id}")
    return TokenOut(access_token=token, role=user.role, name=user.name, institution_id=user.institution_id)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "email": user.email, "name": user.name, "role": user.role,
        "institution_id": user.institution_id,
        "institution_name": user.institution.name if user.institution else None,
    }
