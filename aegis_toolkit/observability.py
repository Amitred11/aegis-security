# core/observability.py
import httpx
import json
import hmac
import hashlib
import time
from aegis_toolkit.config import settings

log_shipper_client = httpx.AsyncClient()

async def ship_audit_log(event: dict):
    """Signs and ships a structured audit log to a central collector."""
    if not settings.log_shipping.enabled:
        print(f"AUDIT_LOG (shipping disabled): {json.dumps(event)}")
        return

    secret = settings.audit_log_signing_key.encode('utf-8')
    timestamp = str(int(time.time()))
    event['timestamp'] = timestamp
    log_string = json.dumps(event, sort_keys=True).encode('utf-8')
    signature = hmac.new(secret, log_string, hashlib.sha256).hexdigest()
    
    headers = {
        'Content-Type': 'application/json',
        'X-Log-Signature': signature,
        'Authorization': f"Bearer {settings.log_shipping.auth_token}"
    }
    
    try:
        await log_shipper_client.post(settings.log_shipping.endpoint, content=log_string, headers=headers)
    except Exception as e:
        print(f"CRITICAL: Log shipping failed to endpoint '{settings.log_shipping.endpoint}': {e}")