from datetime import datetime
from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    institution_id: int | None = None


class ApplicationCreate(BaseModel):
    academic_year: str
    category: str = "EOA"


class FlagDecisionIn(BaseModel):
    decision: str  # ACCEPT or DISMISS
    reason: str


class InspectionDecisionIn(BaseModel):
    status: str  # CONFIRMED or CLEARED
    note: str
