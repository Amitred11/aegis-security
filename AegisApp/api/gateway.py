# api/gateway.py
import httpx
import logging
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from aegis_toolkit.config import settings
from aegis_toolkit.security import get_api_client, ApiClient
from aegis_toolkit.sentry import inspect_request
from aegis_toolkit.threat_intel import check_ip_reputation
from aegis_toolkit.profiler import profile_and_analyze
from aegis_toolkit.transformer import purify_response_body
from aegis_toolkit.authorization import apply_request_enhancements
from api.mobile_endpoints import get_current_user
from aegis_toolkit.cartographer import check_for_shadow_api

router = APIRouter()
audit_logger = logging.getLogger("audit")
proxy_client = httpx.AsyncClient(base_url=settings.backend_target_url)

@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def universal_gateway(
    path: str,
    request: Request,
    client: ApiClient = Depends(get_api_client),
    user_jwt: dict = Depends(get_current_user)
):
    """
    This is the main gateway entry point. It runs all security checks
    and then proxies the request to the backend service.
    """
    body = await request.body()

    try:
        check_for_shadow_api(request.method, request.url.path)
        await check_ip_reputation(request)
        await inspect_request(request, body)
        await profile_and_analyze(client.client_id, request)
        apply_request_enhancements(request, client.role, user_jwt)

    except HTTPException as e:
        audit_logger.critical(f"AUDIT - REQUEST_BLOCKED: Client '{client.client_id}' IP '{request.client.host}' Reason: {e.detail}")
        raise e

    url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
    
    backend_request = proxy_client.build_request(
        method=request.method,
        url=url,
        headers=request.headers.raw,
        content=body
    )
    
    try:
        backend_response = await proxy_client.send(backend_request, stream=True)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Backend service is unavailable.")

    response_body_bytes = await backend_response.aread()
    purified_body = purify_response_body(client.role, response_body_bytes)

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