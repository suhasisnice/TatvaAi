import pyotp
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db

from app.core.security import current_user, decode_token, make_token, verify_password
from app.models.user import User
from app.services.audit import hash_chain as audit
from app.schemas.auth import LoginIn, RefreshIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(uid: int) -> TokenOut:
    return TokenOut(access_token=make_token(uid, "access"), refresh_token=make_token(uid, "refresh"))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        audit.log(db, "anonymous", "auth.login_failed", f"email:{body.email.lower()[:80]}", {"reason": "invalid credentials"})
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    # Users who have not enrolled yet can log in to reach /mfa/setup; once enrolled, OTP is mandatory.
    if user.mfa_enabled:
        if not body.otp:
            raise HTTPException(401, "MFA_REQUIRED")
        if not pyotp.TOTP(user.mfa_secret).verify(body.otp, valid_window=1):
            raise HTTPException(401, "Invalid OTP")
    audit.log(db, user, "auth.login", f"user:{user.id}", {"role": user.role, "mfa": user.mfa_enabled})
    db.commit()
    return _tokens(user.id)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    uid = decode_token(body.refresh_token, "refresh")
    user = db.get(User, uid)
    if not user or not user.active:
        raise HTTPException(401, "Unknown or inactive user")
    return _tokens(uid)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
