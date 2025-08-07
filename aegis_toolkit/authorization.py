# core/authorization.py
from fastapi import Request, HTTPException, status
from fnmatch import fnmatch
from typing import Dict, Any

from .config import Settings

def apply_request_enhancements(request: Request, client_role: str, user_jwt: Dict[str, Any], settings: Settings):
    """
    Applies additional, context-aware security checks to a request. (IDOR Protection)
    
    Refactored to use FastAPI's `request.path_params` for reliable ID extraction,
    removing the brittle regex. The path parameter name is now defined in config.
    """
    path_to_check = request.url.path

    for policy in settings.authorization_policies:
        if policy.match.get("role") == client_role:
            for rule in policy.rules:
                if fnmatch(path_to_check, rule.path_pattern):
                    if rule.enforce_owner and rule.owner_path_param:
                        path_owner_id = request.path_params.get(rule.owner_path_param)
                        
                        jwt_owner_id = user_jwt.get(rule.enforce_owner)
                        
                        if jwt_owner_id and path_owner_id and jwt_owner_id != path_owner_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Forbidden: You do not have permission to access this resource."
                            )
                    
                    return
    return