import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from jose import jwt
from datetime import datetime, timedelta, timezone

from main import settings

from aegis_toolkit.security import get_api_client_factory, get_current_user_factory, ApiClient

get_api_client = get_api_client_factory(settings)
get_current_user = get_current_user_factory(settings)

router = APIRouter(prefix="/auth", tags=["Authentication"])
audit_logger = logging.getLogger("audit")

class LoginRequest(BaseModel):
    email: str
    password: str

def create_access_token(data: dict):
    """Creates a JWT access token for a user."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt

auth_backend_client = httpx.AsyncClient(base_url="http://localhost:8006/auth-service")

@router.post("/login")
async def login(form_data: LoginRequest, client_app: ApiClient = Depends(get_api_client)):
    """
    Handles user login by proxying to an internal authentication service.
    If successful, it issues a JWT from this middleware.
    """
    audit_logger.info(f"App '{client_app.client_id}' attempting user login.")

    try:
        response = await auth_backend_client.post("/login", json=form_data.model_dump())
        response.raise_for_status()

        user_data_from_backend = response.json()
        
        if "user_id" not in user_data_from_backend or "role" not in user_data_from_backend:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Backend auth service did not return required user data."
            )

        access_token = create_access_token(data={
            "user_id": user_data_from_backend["user_id"],
            "role": user_data_from_backend["role"],
        })
        
        return {"access_token": access_token, "token_type": "bearer"}

    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail") if e.response.content else e.response.text
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except httpx.RequestError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Authentication service is currently unavailable."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An unexpected error occurred during login: {e}"
        )
    
@router.post("/refresh")
async def refresh_token(
    client_app: ApiClient = Depends(get_api_client),
    current_user: dict = Depends(get_current_user)
):
    """
    Accepts a valid access token and returns a new one with a fresh expiration time.
    """
    if not current_user.get("user_id"):
        raise HTTPException(status_code=401, detail="Invalid or expired token provided.")

    new_access_token = create_access_token(data={
        "user_id": current_user["user_id"],
        "role": current_user["role"],
    })
    
    audit_logger.info(f"Token refreshed for user_id: {current_user['user_id']}")
    return {"access_token": new_access_token, "token_type": "bearer"}