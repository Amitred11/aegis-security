# core/cartographer.py
import httpx
import logging
from fastapi import HTTPException
from .config import Settings

KNOWN_ENDPOINTS = set()
SHADOW_ENDPOINTS = set()
audit_logger = logging.getLogger("audit")

async def initialize_api_spec(settings: Settings):
    """On startup, load the official OpenAPI spec to build a map of known endpoints."""
    spec_url = settings.api_discovery.openapi_spec_url
    if not spec_url:
        print("WARNING: No OpenAPI spec URL provided. API discovery will be less effective.")
        return
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(spec_url)
            response.raise_for_status()
            spec = response.json()
            for path, methods in spec.get('paths', {}).items():
                for method in methods:
                    KNOWN_ENDPOINTS.add(f"{method.upper()} {path}")
        print(f"Cartographer initialized with {len(KNOWN_ENDPOINTS)} known endpoints from spec.")
    except Exception as e:
        print(f"ERROR: Cartographer failed to initialize from spec URL '{spec_url}': {e}")


def check_for_shadow_api(method: str, path_template: str, settings: Settings):
    """
    Check if a requested endpoint is in the official spec.
    If not, it's a "shadow API" and should be flagged or blocked.
    """
    endpoint_signature = f"{method.upper()} {path_template}"
    
    if endpoint_signature in KNOWN_ENDPOINTS or endpoint_signature in SHADOW_ENDPOINTS:
        return
        
    SHADOW_ENDPOINTS.add(endpoint_signature)
    
    log_message = f"SHADOW_API_DISCOVERED: Undocumented endpoint was accessed: '{endpoint_signature}'"
    audit_logger.critical(f"AUDIT - {log_message}")

    if settings.api_discovery.on_shadow_api_discovered == 'block':        
        raise HTTPException(
            status_code=501, 
            detail="This API endpoint is not implemented or has been deprecated."
        )