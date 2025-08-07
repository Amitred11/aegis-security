# api/health.py
import asyncio
import httpx
from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from typing import List
from urllib.parse import urlparse

from aegis_toolkit.config import settings
from aegis_toolkit.cache import redis_client, CACHE_ENABLED, USE_REDIS

router = APIRouter()
health_check_client = httpx.AsyncClient(timeout=5.0)

class ServiceStatus(BaseModel):
    service: str
    status: str
    details: str = "OK"

class HealthResponse(BaseModel):
    overall_status: str
    services: List[ServiceStatus]

@router.get("/health", tags=["Monitoring"], response_model=HealthResponse)
async def get_health(response: Response):
    """Checks the status of the cache and configured backend services."""
    service_statuses = []
    is_healthy = True

    if CACHE_ENABLED:
        cache_type = "redis" if USE_REDIS else "in-memory"
        if USE_REDIS and redis_client:
            try:
                await redis_client.ping()
                service_statuses.append(ServiceStatus(service=f"cache ({cache_type})", status="ok"))
            except Exception as e:
                is_healthy = False
                service_statuses.append(ServiceStatus(
                    service=f"cache ({cache_type})", status="error", details=str(e)
                ))
        else:
            service_statuses.append(ServiceStatus(service=f"cache ({cache_type})", status="ok"))
    else:
        service_statuses.append(ServiceStatus(service="cache", status="disabled"))

    backend_hosts = {
        urlparse(query.backend_url).netloc
        for agg in settings.aggregations
        for query in agg.queries
    }
    
    check_tasks = [_check_backend_service(f"http://{host}") for host in backend_hosts]
    results = await asyncio.gather(*check_tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, ServiceStatus):
            service_statuses.append(res)
            if res.status == "error":
                is_healthy = False
        else:
            is_healthy = False
            service_statuses.append(ServiceStatus(service="unknown_backend", status="error", details=str(res)))

    overall_status = "ok" if is_healthy else "error"
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(overall_status=overall_status, services=service_statuses)


async def _check_backend_service(url: str) -> ServiceStatus:
    try:
        response = await health_check_client.head(url)
        if response.status_code < 500:
            return ServiceStatus(service=f"backend ({url})", status="ok")
        else:
            return ServiceStatus(service=f"backend ({url})", status="error", details=f"Received status {response.status_code}")
    except httpx.RequestError as e:
        return ServiceStatus(service=f"backend ({url})", status="error", details=f"Connection error: {e.__class__.__name__}")