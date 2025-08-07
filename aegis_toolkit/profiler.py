import time
import math
import json
from collections import defaultdict
from fastapi import Request, HTTPException
from .config import Settings
from aegis_toolkit.cache import redis_client

def _shannon_entropy(data: list) -> float:
    """Calculates the randomness (entropy) of a sequence of path requests."""
    if not data:
        return 0.0
    
    frequency = defaultdict(int)
    for item in data:
        frequency[item] += 1
        
    entropy = 0.0
    data_len = float(len(data))
    for count in frequency.values():
        prob = count / data_len
        entropy -= prob * math.log(prob, 2)
        
    return entropy

async def profile_and_analyze(client_id: str, request: Request, settings: Settings):
    """
    Builds a client profile in Redis and analyzes behavior in real-time.
    Checks for:
    1. Client Fingerprint Consistency: Detects if headers like User-Agent change.
    2. Path Traversal Entropy: Detects random, non-sequential URL scanning.
    """
    if not redis_client:
        print("WARNING: Redis not available, skipping client profiling.")
        return

    profile_key = f"profile:{client_id}"
    path_history_key = f"profile:paths:{client_id}"
    
    current_fingerprint = (
        request.headers.get("user-agent", "") + 
        request.headers.get("accept-language", "")
    )
    
    existing_fingerprint_bytes = await redis_client.hget(profile_key, "fingerprint")
    existing_fingerprint = existing_fingerprint_bytes.decode('utf-8') if existing_fingerprint_bytes else None

    if not existing_fingerprint:
        pipe = redis_client.pipeline()
        pipe.hset(profile_key, "fingerprint", current_fingerprint)
        pipe.expire(profile_key, 3600)
        await pipe.execute()
        return
    
    if settings.behavioral_analysis.enforce_header_consistency:
        if existing_fingerprint != current_fingerprint:
            raise HTTPException(
                status_code=403, 
                detail="Forbidden: Client fingerprint has changed. Please re-authenticate."
            )

    path_segment = request.url.path.split('/')[1] if len(request.url.path.split('/')) > 1 else 'root'
    pipe = redis_client.pipeline()
    pipe.lpush(path_history_key, path_segment)
    pipe.ltrim(path_history_key, 0, 19)
    pipe.expire(path_history_key, 3600)
    await pipe.execute()

    path_history = await redis_client.lrange(path_history_key, 0, -1)
    
    entropy = _shannon_entropy(path_history)
    if entropy > settings.behavioral_analysis.max_path_entropy:
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Suspicious browsing pattern detected (high entropy)."
        )