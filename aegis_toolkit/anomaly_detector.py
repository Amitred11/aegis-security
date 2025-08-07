# core/anomaly_detector.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException

BEHAVIOR_LOG = defaultdict(lambda: {"error_count": [], "path_requests": []})
ERROR_THRESHOLD = 10
PATH_ENUMERATION_THRESHOLD = 20

def track_request(client_id: str, request: Request, is_error: bool = False):
    """Tracks client behavior to detect anomalies."""
    now = time.time()
    log = BEHAVIOR_LOG[client_id]

    log["error_count"] = [t for t in log["error_count"] if now - t < 60]
    log["path_requests"] = [t for t in log["path_requests"] if now - t < 60]

    if is_error:
        log["error_count"].append(now)
        if len(log["error_count"]) > ERROR_THRESHOLD:
            raise HTTPException(status_code=429, detail="Too many errors. Your access has been temporarily restricted.")

    log["path_requests"].append(now)
    if len(log["path_requests"]) > PATH_ENUMERATION_THRESHOLD:
        raise HTTPException(status_code=429, detail="Request velocity too high. Your access has been temporarily restricted.")