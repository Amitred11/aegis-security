# core/authorization.py
import re 
from fastapi import Request, HTTPException, status
from fnmatch import fnmatch
from typing import Dict, Any

from .config import Settings

def apply_request_enhancements(request: Request, client_role: str, user_jwt: Dict[str, Any], settings: Settings):
    path_to_check = request.url.path

    for policy in settings.authorization_policies:
        if policy.match.get("role") == client_role:
            for rule in policy.rules:
                if not rule.enforce_owner and fnmatch(path_to_check, rule.path_pattern):
                    return

                if rule.enforce_owner:
                    match = re.search(r"/users/([^/]+)", path_to_check)
                    
                    if match:
                        path_owner_id = match.group(1)
                        jwt_owner_id = user_jwt.get(rule.enforce_owner)
                        
                        if jwt_owner_id and path_owner_id and jwt_owner_id != path_owner_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Forbidden: You do not have permission to access this resource."
                            )
                        return
    return