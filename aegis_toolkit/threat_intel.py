# core/threat_intel.py
import httpx
import logging
from fastapi import Request, HTTPException
from .config import Settings

audit_logger = logging.getLogger("audit")
ABUSEIPDB_KEY = Settings.abuseipdb_api_key

async def check_ip_reputation(request: Request, settings: Settings):
    """Checks the client's IP against the AbuseIPDB blacklist."""
    ABUSEIPDB_KEY = settings.abuseipdb_api_key
    if not ABUSEIPDB_KEY:
        return

    client_ip = request.client.host
    
    headers = {'Key': ABUSEIPDB_KEY, 'Accept': 'application/json'}
    params = {'ipAddress': client_ip, 'maxAgeInDays': '90'}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("https://api.abuseipdb.com/api/v2/check", headers=headers, params=params)
            if response.status_code == 200:
                data = response.json().get('data', {})
                confidence_score = data.get('abuseConfidenceScore', 0)
                if confidence_score >= settings.abuseipdb_confidence_minimum:
                    audit_logger.critical(f"AUDIT - IP_BLACKLISTED: IP '{client_ip}' blocked due to abuse score of {confidence_score}.")
                    raise HTTPException(status_code=403, detail="Forbidden: Your IP address is listed as malicious.")
        except Exception as e:
            audit_logger.error(f"Could not check IP reputation: {e}")