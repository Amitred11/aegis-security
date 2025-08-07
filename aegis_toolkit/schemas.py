# models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Optional

class ErrorDetail(BaseModel):
    code: str
    message: str

class ErrorResponse(BaseModel):
    error: ErrorDetail

class ApiClient(BaseModel):
    client_id: str
    api_key: str
    role: str
    allowed_ips: List[str] = []
