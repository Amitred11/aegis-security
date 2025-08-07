# aegis_toolkit/security.py

from fastapi import HTTPException, status, Depends
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import jwt, JWTError
from .config import Settings, ApiClient

def get_api_client_factory(settings: Settings):
    """Factory that returns the get_api_client dependency function."""
    api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)
    API_CLIENTS_BY_KEY = {client.api_key: client for client in settings.api_clients}

    async def get_api_client(api_key: str = Depends(api_key_header_scheme)) -> ApiClient:
        if api_key and api_key in API_CLIENTS_BY_KEY:
            return API_CLIENTS_BY_KEY[api_key]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return get_api_client

def get_current_user_factory(settings: Settings):
    """Factory that returns the get_current_user dependency function."""
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
    
    async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
        if token is None:
            return {}
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
            return payload
        except JWTError:
            raise credentials_exception
    return get_current_user