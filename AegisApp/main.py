import uvicorn
import logging
import sys
import json
from fastapi import FastAPI
from contextlib import asynccontextmanager

from api import bff_endpoints, auth, health, admin
from aegis_toolkit.config import Settings
from aegis_toolkit.cartographer import initialize_api_spec
from aegis_toolkit.cache import initialize_cache, redis_client
from aegis_toolkit.toolkit import create_security_shield

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
import time

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    logging.info("--- Aegis Gateway Starting Up ---")
    initialize_cache(settings)
    await initialize_api_spec(settings)
    
    yield
    
    logging.info("--- Aegis Gateway Shutting Down ---")
    if redis_client:
        await redis_client.close()
        logging.info("Redis connection closed.")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
        }
        if record.exc_info:
            log_record['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

for handler in logger.handlers:
    logger.removeHandler(handler)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

logging.info("Logging configured for JSON output.")

settings = Settings(_env_file=".env")

app = FastAPI(
    title="Aegis Security Gateway",
    description="An integrable, zero-trust security gateway and BFF with a multi-layered WAF.",
    version="3.0.0", # Bump the version to reflect the new WAF!
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    if "/admin" in request.url.path or "/health" in request.url.path:
        return await call_next(request)
    try:
        await limiter.check(request)
    except RateLimitExceeded as e:
        return _rate_limit_exceeded_handler(request, e)
    return await call_next(request)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("--- Aegis Gateway Starting Up ---")
    initialize_cache(settings)
    await initialize_api_spec(settings)
    yield
    logging.info("--- Aegis Gateway Shutting Down ---")
    if redis_client:
        await redis_client.close()
        logging.info("Redis connection closed.")

app = FastAPI(
    title="Aegis",
    description="An integrable, zero-trust security gateway and mobile BFF.",
    version="2.1.0",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(bff_endpoints.router)
app.include_router(admin.router)

security_shield_router = create_security_shield(settings=settings)
app.include_router(security_shield_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)