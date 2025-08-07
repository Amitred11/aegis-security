# core/waf.py
import re
import json
import logging
import html
from fnmatch import fnmatch
from fastapi import Request, HTTPException
from urllib.parse import unquote

from .config import Settings, WAFRule
from .waf_rules import ALL_PATTERNS
from .request_schemas import SCHEMA_REGISTRY
from pydantic import ValidationError

audit_logger = logging.getLogger("audit")

def _canonicalize_input(data: str) -> str:
    """
    Normalizes input by decoding, converting to lowercase, and removing null bytes
    to defeat common WAF evasion techniques.
    """
    if not data:
        return ""
    
    decoded_data = data
    try:
        for _ in range(3):
            new_decoded_data = unquote(decoded_data)
            if new_decoded_data == decoded_data:
                break
            decoded_data = new_decoded_data

        decoded_data = html.unescape(decoded_data)

        decoded_data = decoded_data.replace('\x00', '')
        
        decoded_data = decoded_data.lower()

    except Exception as e:
        audit_logger.warning(f"WAF: Input canonicalization failed for data snippet '{data[:50]}...': {e}")
        pass 
        
    return decoded_data

def _perform_signature_detection(text_to_scan: str, location: str):
    """Scans text against the full OWASP-inspired regex pattern set."""
    for pattern in ALL_PATTERNS:
        if re.search(pattern, text_to_scan):
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
    Inspects an incoming request against all WAF rules.
    1. Canonicalizes input to defeat evasion.
    2. Performs global signature checks.
    3. Applies specific, path-based rules (schema validation, pattern matching, etc.).
    """
    canonical_query_str = _canonicalize_input(request.url.query)
    raw_body_str = body.decode('utf-8', 'ignore')
    canonical_body_str = _canonicalize_input(raw_body_str)

    _perform_signature_detection(canonical_query_str, "query parameters")
    _perform_signature_detection(canonical_body_str, "request body")
    
    for rule in settings.waf_rules:
        if not fnmatch(request.url.path, rule.path_pattern):
            continue
        if "*" not in rule.methods and request.method not in rule.methods:
            continue


        if rule.body_schema:
            schema = SCHEMA_REGISTRY.get(rule.body_schema)
            if not schema:
                audit_logger.error(f"WAF: Unknown schema '{rule.body_schema}' defined in rule '{rule.name}'")
                continue
            
            try:
                body_json = json.loads(raw_body_str)
                schema.model_validate(body_json)
            except (json.JSONDecodeError, ValidationError) as e:
                audit_logger.warning(f"AUDIT - WAF_SCHEMA_VIOLATION: Rule '{rule.name}' triggered. Reason: {e}")
                raise HTTPException(status_code=422, detail=f"Invalid request body format: {str(e)}")

        elif rule.pattern:
            pattern = re.compile(rule.pattern)
            if "body" in rule.inspect_locations and pattern.search(canonical_body_str):
                _trigger_violation(rule, "request body")
            if "query_params" in rule.inspect_locations and pattern.search(canonical_query_str):
                _trigger_violation(rule, "query parameters")
        elif rule.type == 'graphql_depth_check':
            if not rule.max_depth: continue
            try:
                gql_body = json.loads(raw_body_str)
                if _get_query_depth(gql_body) > rule.max_depth:
                    _trigger_violation(rule, "GraphQL query depth")
            except (json.JSONDecodeError, AttributeError):
                continue
        elif rule.type == 'graphql_cost_check' and "body" in rule.inspect_locations:
            if not rule.max_cost: continue
            try:
                cost = len(re.findall(r'[:\s](\w+)\s*[{]', canonical_body_str))
                if cost > rule.max_cost:
                   _trigger_violation(rule, f"GraphQL query cost ({cost})")
            except Exception:
                continue

def _trigger_violation(rule, location):
    audit_logger.critical(f"AUDIT - WAF_VIOLATION: Rule '{rule.name}' triggered on '{location}'")
    if rule.action == 'block':
        raise HTTPException(status_code=403, detail="Forbidden: Malicious content detected.")