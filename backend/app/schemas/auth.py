from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str
    otp: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    institution_id: int | None
    mfa_enabled: bool

    model_config = {"from_attributes": True}


class OtpIn(BaseModel):
    otp: str
