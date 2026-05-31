import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class TokenRequest(BaseModel):
    api_key: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserSignup(BaseModel):
    organization_name: str
    email: EmailStr
    password: str
    full_name: str | None = None


class SignupResponse(BaseModel):
    status: str
    message: str
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ClientCreate(BaseModel):
    name: str


class ClientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    api_key: str
    is_active: bool
    created_at: datetime


class ClientListResponse(BaseModel):
    clients: list[ClientResponse]
    total: int


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str | None
    status: str
    role: str
    created_at: datetime


class UserMeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    status: str
    role: str
    organization: OrganizationResponse


class ApproveResponse(BaseModel):
    message: str
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    message: str
