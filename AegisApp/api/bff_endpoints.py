# api/bff_endpoints.py
import asyncio
import logging
import httpx
import re
from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Any, Dict
from asyncio import TimeoutError

from main import settings
from aegis_toolkit.config import Aggregation
from aegis_toolkit.security import get_api_client_factory, get_current_user_factory
from aegis_toolkit.cache import cache_response

router = APIRouter(tags=["BFF"])
audit_logger = logging.getLogger("audit")
http_client = httpx.AsyncClient(timeout=10.0)

get_api_client = get_api_client_factory(settings)
get_current_user = get_current_user_factory(settings)

def _get_nested_key(d: dict, key_path: str):
    keys = key_path.split('.')
    val = d
    for key in keys:
        if isinstance(val, dict): val = val.get(key)
        else: return None
    return val

def _format_string_with_context(template_str: str, context: dict) -> str:
    placeholders = re.findall(r'\{([a-zA-Z0-9_.]*)\}', template_str)
    for placeholder in placeholders:
        value = _get_nested_key(context, placeholder)
        template_str = template_str.replace(f'{{{placeholder}}}', str(value) if value is not None else '')
    return template_str

def _inject_context_data(template: Any, context: Dict[str, Any]) -> Any:
    if isinstance(template, str): return _format_string_with_context(template, context)
    if isinstance(template, dict): return {k: _inject_context_data(v, context) for k, v in template.items()}
    if isinstance(template, list): return [_inject_context_data(i, context) for i in template]
    return template

def _apply_adapter(data: dict, adapter_config: dict) -> dict:
    if not adapter_config: return data
    selected_data = {}
    if "select" in adapter_config:
        for field in adapter_config["select"]:
            if field in data: selected_data[field] = data[field]
    else: selected_data = data.copy()
    if "rename" in adapter_config:
        for old_name, new_name in adapter_config["rename"].items():
            if old_name in selected_data: selected_data[new_name] = selected_data.pop(old_name)
    return selected_data

async def run_sub_request(query_config: dict, context: dict):    
    final_backend_url = _inject_context_data(query_config['backend_url'], context)
    request_body = _inject_context_data(query_config.get('body'), context)
    request_params = _inject_context_data(query_config.get('params'), context)
    try:
        response = await http_client.request(
            method=query_config['http_method'], url=final_backend_url,
            json=request_body, params=request_params
        )
        response.raise_for_status()
        data = response.json()
        if query_config.get('adapter'):
            if isinstance(data, list): return [_apply_adapter(item, query_config['adapter']) for item in data]
            return _apply_adapter(data, query_config['adapter'])
        return data
    except httpx.HTTPStatusError as e:
        audit_logger.error(f"BFF Backend error for '{query_config['name']}': {e.response.status_code}")
        return {"error": f"Backend error: {e.response.status_code}", "detail": e.response.text}
    except httpx.RequestError as e:
        audit_logger.error(f"BFF Backend connection error for '{query_config['name']}': {e}")
        return {"error": "Backend service unreachable"}

def create_aggregation_endpoint(agg_config: Aggregation):
    @router.api_route(agg_config.public_path, methods=["GET", "POST"])
    @cache_response()
    async def dynamic_aggregation_endpoint(
        request: Request,
        current_user: dict = Depends(get_current_user),
        app_client: dict = Depends(get_api_client)
    ):
        if agg_config.required_role != "mobile_guest":
            if not current_user: raise HTTPException(status_code=401, detail="Authentication required")
            if current_user.get('role') != agg_config.required_role: raise HTTPException(status_code=403, detail="Forbidden")
        
        context = {"jwt": current_user, "path_params": request.path_params, "query_params": dict(request.query_params)}
        
        try:
            tasks = [run_sub_request(q.model_dump(), context) for q in agg_config.queries]
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5.0)
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Gateway Timeout: Upstream services took too long to respond.")

        return {query.name: result for query, result in zip(agg_config.queries, results)}

for agg in settings.aggregations:
    create_aggregation_endpoint(agg)