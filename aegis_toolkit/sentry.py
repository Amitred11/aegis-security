import re
import json
import logging
from fastapi import Request, HTTPException
from urllib.parse import unquote
from .config import Settings
from .waf_rules import ALL_PATTERNS

audit_logger = logging.getLogger("audit")

def _perform_signature_detection(text_to_scan: str, location: str):
    """Scans text against the full OWASP-inspired regex pattern set."""
    for pattern in ALL_PATTERNS:
        if re.search(pattern, text_to_scan, re.IGNORECASE):
            audit_logger.critical(f"AUDIT - WAF_SIGNATURE_VIOLATION: Pattern '{pattern}' triggered on '{location}'")
            raise HTTPException(status_code=403, detail="Forbidden: Malicious signature detected.")

def _get_query_depth(query: dict, max_depth=0) -> int:
    if not isinstance(query, dict): return max_depth
    current_depth = max_depth + 1
    max_child_depth = current_depth
    for key, value in query.items():
        if isinstance(value, dict):
            child_depth = _get_query_depth(value, current_depth)
            max_child_depth = max(max_child_depth, child_depth)
        elif isinstance(value, list):
            for item in value:
                child_depth = _get_query_depth(item, current_depth)
                max_child_depth = max(max_child_depth, child_depth)
    return max_child_depth
async def inspect_request(request: Request, body: bytes, settings: Settings):
    """
    Inspects an incoming request against all Sentry (WAF) rules AND the
    core signature database.
    """
    decoded_query_str = unquote(request.url.query)
    decoded_body_str = unquote(body.decode('utf-8', 'ignore'))

    _perform_signature_detection(decoded_query_str, "query parameters")
    _perform_signature_detection(decoded_body_str, "request body")
    
    for rule in settings.sentry_rules:
        if rule.pattern:
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            if "body" in rule.inspect_locations and pattern.search(decoded_body_str):
                _trigger_violation(rule, "request body")
            if "query_params" in rule.inspect_locations and pattern.search(decoded_query_str):
                _trigger_violation(rule, "query parameters")

        elif rule.type == 'graphql_depth_check' and "body" in rule.inspect_locations:
            try:
                gql_body = json.loads(decoded_body_str)
                if _get_query_depth(gql_body) > rule.max_depth:
                    _trigger_violation(rule, "GraphQL query depth")
            except (json.JSONDecodeError, AttributeError):
                continue
        elif rule.type == 'graphql_cost_check' and "body" in rule.inspect_locations:
            try:
                cost = len(re.findall(r'[:\s](\w+)\s*[{]', decoded_body_str))
                if cost > rule.max_cost:
                   _trigger_violation(rule, f"GraphQL query cost ({cost})")
            except Exception:
                continue

def _trigger_violation(rule, location):
    
    audit_logger.critical(f"AUDIT - WAF_VIOLATION: Rule '{rule.name}' triggered on '{location}'")
    if rule.action == 'block':
        raise HTTPException(status_code=403, detail="Forbidden: Malicious content detected.")