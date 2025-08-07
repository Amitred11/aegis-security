# aegis_toolkit/toolkit.py

import httpx
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .config import Settings, ApiClient
from .waf import inspect_request
from .threat_intel import check_ip_reputation
from .profiler import profile_and_analyze
from .transformer import purify_response_body
from .authorization import apply_request_enhancements
from .security import get_api_client_factory, get_current_user_factory
from .cartographer import check_for_shadow_api
from .anomaly_detector import track_request

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
        is_error = False
        try:
            check_for_shadow_api(request.method, path, settings)
            await check_ip_reputation(request, settings)
            await inspect_request(request, body, settings)
            await profile_and_analyze(client.client_id, request, settings)
            apply_request_enhancements(request, client.role, user_jwt, settings)

        except HTTPException as e:
            is_error = True
            audit_logger.critical(f"AUDIT - REQUEST_BLOCKED: Client '{client.client_id}' IP '{request.client.host}' Reason: {e.detail}")
            raise e
        finally:
            try:
                track_request(client.client_id, request, is_error=is_error)
            except HTTPException as e:
                audit_logger.critical(f"AUDIT - ANOMALY_BLOCKED: Client '{client.client_id}' IP '{request.client.host}' Reason: {e.detail}")
                raise e

        url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
        backend_request = proxy_client.build_request(
            method=request.method, url=url, headers=request.headers.raw, content=body
        )
        try:
            backend_response = await proxy_client.send(backend_request, stream=True)
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Backend service is unavailable.")
        
        response_body_bytes = await backend_response.aread()
        purified_body = purify_response_body(client.role, response_body_bytes, settings)
        
        response_headers = backend_response.headers
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        for key in excluded_headers:
            if key in response_headers:
                del response_headers[key]
        
        return StreamingResponse(
            content=iter([purified_body]),
            status_code=backend_response.status_code,
            headers=response_headers,
            media_type=backend_response.headers.get("content-type"),
        )
        
    return router