# aegis_toolkit/security.py

from fastapi import HTTPException, status, Depends, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import jwt, JWTError
from .config import Settings, ApiClient

def get_api_client_factory(settings: Settings):
    """Factory that returns the get_api_client dependency function."""
    api_key_header_scheme = APIKeyHeader(name="x-api-key", auto_error=False)
    API_CLIENTS_BY_KEY = {client.api_key: client for client in settings.api_clients}

    async def get_api_client(request: Request, api_key: str = Depends(api_key_header_scheme)) -> ApiClient:
        if not api_key or api_key not in API_CLIENTS_BY_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key"
            )
            
        client = API_CLIENTS_BY_KEY[api_key]
        
        if client.allowed_ips:
            if request.client.host not in client.allowed_ips:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: This IP address is not allowed to use this API key."
                )
        return client
        
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