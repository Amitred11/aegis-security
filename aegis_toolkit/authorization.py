# core/authorization.py
import re 
from fastapi import Request, HTTPException, status
from fnmatch import fnmatch
from typing import Dict, Any

from .config import Settings

def apply_request_enhancements(request: Request, client_role: str, user_jwt: Dict[str, Any], settings: Settings):
    """Applies additional, context-aware security checks to a request.

    This function acts as the IDOR (Insecure Direct Object Reference) protection
    layer. It iterates through the authorization policies defined in the settings.
    If a policy matching the client's role and request path has an `enforce_owner`
    rule, it compares the owner ID from the JWT against the ID in the URL.

    Note: This function does NOT block requests by default. It only enhances
    security for matching rules. If no rule matches, the request is allowed
    to proceed to the backend for final authorization.

    Args:
        request: The incoming FastAPI Request object.
        client_role: The role of the authenticated API client (e.g., "mobile_app_standard").
        user_jwt: The decoded payload of the user's JSON Web Token.
        settings: The application's configuration object.

    Raises:
        HTTPException(403): If an `enforce_owner` check is triggered and the
                            user ID in the JWT does not match the user ID in the path.
    """
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