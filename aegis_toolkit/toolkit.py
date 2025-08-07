# aegis_toolkit/toolkit.py

import httpx
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

# Import all the security modules from WITHIN the toolkit
from .config import Settings, ApiClient
from .sentry import inspect_request
from .threat_intel import check_ip_reputation
from .profiler import profile_and_analyze
from .transformer import purify_response_body
from .authorization import apply_request_enhancements
from .security import get_api_client_factory, get_current_user_factory
from aegis_toolkit.cartographer import check_for_shadow_api

def create_security_shield(settings: Settings) -> APIRouter:
    """
    This is the main factory function for the Aegis Toolkit.
    It takes a settings object and returns a pre-configured FastAPI APIRouter
    that acts as a universal security gateway.
    """
    router = APIRouter()
    audit_logger = logging.getLogger("audit")
    proxy_client = httpx.AsyncClient(base_url=settings.backend_target_url)

    get_api_client = get_api_client_factory(settings)
    get_current_user = get_current_user_factory(settings)

    @router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def universal_gateway(
        path: str,
        request: Request,
        client: ApiClient = Depends(get_api_client),
        user_jwt: dict = Depends(get_current_user)
    ):
        body = await request.body()
        try:
           check_for_shadow_api(request.method, request.url.path, settings)
           await check_ip_reputation(request, settings)
           await inspect_request(request, body, settings)
           await profile_and_analyze(client.client_id, request, settings)
           apply_request_enhancements(request, client.role, user_jwt, settings)
        except HTTPException as e:
            audit_logger.critical(f"AUDIT - REQUEST_BLOCKED: Client '{client.client_id}' Reason: {e.detail}")
            raise e

        # Proxying logic remains the same
        url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
        backend_request = proxy_client.build_request(
            method=request.method, url=url, headers=request.headers.raw, content=body
        )
        try:
            backend_response = await proxy_client.send(backend_request, stream=True)
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Backend service is unavailable.")
        
        # PII Purification
        response_body_bytes = await backend_response.aread()
        purified_body = purify_response_body(client.role, response_body_bytes, settings)
        
        # ... StreamingResponse logic remains the same ...
        # ...
        
    return router