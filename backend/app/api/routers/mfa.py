import base64
import io

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models.user import User
from app.schemas.auth import OtpIn
from app.services.audit import hash_chain as audit

router = APIRouter(prefix="/mfa", tags=["mfa"])


@router.post("/setup")
def setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.mfa_enabled:
        raise HTTPException(409, "MFA already enabled")
    user.mfa_secret = pyotp.random_base32()
    db.add(user)
    db.commit()
    uri = pyotp.TOTP(user.mfa_secret).provisioning_uri(user.email, issuer_name="TatvaAI")
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    return {"secret": user.mfa_secret, "uri": uri, "qr_png_base64": base64.b64encode(buf.getvalue()).decode()}


@router.post("/verify")
def verify(body: OtpIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(body.otp, valid_window=1):
        raise HTTPException(400, "Invalid OTP")
    user.mfa_enabled = True
    audit.log(db, user, "mfa.enabled", f"user:{user.id}", {})
    db.add(user)
    db.commit()
    return {"mfa_enabled": True}
