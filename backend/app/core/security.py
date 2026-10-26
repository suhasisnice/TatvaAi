from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User

ROLES = ("institution", "officer", "inspector")
_bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def make_token(user_id: int, kind: str) -> str:
    ttl = timedelta(minutes=settings.access_minutes) if kind == "access" else timedelta(days=settings.refresh_days)
    payload = {"sub": str(user_id), "type": kind, "exp": datetime.now(timezone.utc) + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, kind: str) -> int:
    try:
        p = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if p.get("type") != kind:
        raise HTTPException(401, "Wrong token type")
    return int(p["sub"])


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    user = db.get(User, decode_token(cred.credentials, "access"))
    if not user or not user.active:
        raise HTTPException(401, "Unknown or inactive user")
    return user


def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return user

    return dep
