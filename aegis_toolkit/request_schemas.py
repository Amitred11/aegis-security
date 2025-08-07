# core/request_schemas.py
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    full_name: str

class UpdateUserPreferencesRequest(BaseModel):
    user_id: UUID
    enable_notifications: bool
    theme: str

SCHEMA_REGISTRY = {
    "CreateUserRequest": CreateUserRequest,
    "UpdateUserPreferencesRequest": UpdateUserPreferencesRequest,
}