# api/admin.py

import logging
import yaml
from fastapi import APIRouter, Depends, Body, HTTPException, status

from aegis_toolkit.cartographer import KNOWN_ENDPOINTS, SHADOW_ENDPOINTS
from aegis_toolkit.security import get_api_client_factory, ApiClient
from main import settings

router = APIRouter(prefix="/admin", tags=["Administration"])
audit_logger = logging.getLogger("audit")
get_api_client = get_api_client_factory(settings)

async def is_admin_client(client: ApiClient = Depends(get_api_client)):
    """
    A specific dependency that ensures the API client has the 'admin' role.
    """
    if client.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This action requires admin privileges."
        )
    return client

@router.post("/spec", dependencies=[Depends(is_admin_client)])
async def update_api_spec(
    spec_content: str = Body(..., media_type="text/plain")
):
    """
    Dynamically updates the API specification for the Cartographer module.
    This allows an admin to load a new API map without restarting the gateway.
    Accepts raw YAML or JSON as the request body.
    """
    global KNOWN_ENDPOINTS, SHADOW_ENDPOINTS
    
    try:
        spec = yaml.safe_load(spec_content)
        if not isinstance(spec, dict) or 'paths' not in spec:
            raise HTTPException(status_code=400, detail="Invalid OpenAPI spec format. Must be a valid JSON or YAML object with a 'paths' key.")
        KNOWN_ENDPOINTS.clear()
        SHADOW_ENDPOINTS.clear()

        for path, methods in spec.get('paths', {}).items():
            for method in methods:
                KNOWN_ENDPOINTS.add(f"{method.upper()} {path}")
        
        message = f"Cartographer dynamically re-initialized with {len(KNOWN_ENDPOINTS)} known endpoints."
        print(f"INFO: {message}")
        audit_logger.warning(f"AUDIT - API_SPEC_UPDATED: {message}")
        
        return {"status": "success", "message": message}

    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse YAML/JSON content: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")