# core/cache.py
import redis.asyncio as redis
import json
import time
from functools import wraps
from .config import Settings

CACHE_ENABLED = False
USE_REDIS = False
IN_MEMORY_CACHE = {}
redis_client = None

def initialize_cache(settings: Settings):
    """Initializes cache based on provided settings."""
    global CACHE_ENABLED, USE_REDIS, redis_client, IN_MEMORY_CACHE
    if settings.redis_url:
     try:
        redis_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
        redis_client = redis.Redis(connection_pool=redis_pool)
        
        CACHE_ENABLED = True
        USE_REDIS = True
        print("Redis cache connected successfully.")
     except Exception as e:
        CACHE_ENABLED = True
        USE_REDIS = False
        print(f"WARNING: Redis connection failed ({e}). Falling back to simple in-memory cache.")
     else:
       CACHE_ENABLED = True
       USE_REDIS = False
       print("No Redis URL configured. Using simple in-memory cache.")

async def _get_from_cache(key: str):
    if USE_REDIS and redis_client:
        return await redis_client.get(key)
    else:
        if key in IN_MEMORY_CACHE:
            value, expiry = IN_MEMORY_CACHE[key]
            if time.time() < expiry:
                return value
            else:
                del IN_MEMORY_CACHE[key]
        return None

async def _set_in_cache(key: str, value: str, ttl_seconds: int):
    if USE_REDIS and redis_client:
        await redis_client.setex(key, ttl_seconds, value)
    else:
        expiry = time.time() + ttl_seconds
        IN_MEMORY_CACHE[key] = (value, expiry)

def cache_response(ttl_seconds: int = 60):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not CACHE_ENABLED:
                return await func(*args, **kwargs)

            agg_config = args[0]
            user_context = args[1] if len(args) > 1 else {}
            key_parts = [func.__name__, agg_config.public_path, user_context.get("user_id", "anon")]
            cache_key = ":".join(key_parts)

            cached_result_str = await _get_from_cache(cache_key)
            if cached_result_str:
                print(f"CACHE HIT: {cache_key}")
                return json.loads(cached_result_str)

            print(f"CACHE MISS: {cache_key}")
            result = await func(*args, **kwargs)
            await _set_in_cache(cache_key, json.dumps(result), ttl_seconds)
            return result
        return wrapper
    return decorator