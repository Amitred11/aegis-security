import uvicorn
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from aegis_toolkit.config import Settings
from aegis_toolkit.cartographer import initialize_api_spec
from aegis_toolkit.cache import initialize_cache, redis_client
from aegis_toolkit.toolkit import create_security_shield

from api import auth, health, mobile_endpoints, admin

settings = Settings(_env_file=".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- Aegis Gateway Starting Up ---")
    initialize_cache(settings)
    await initialize_api_spec(settings)
    yield
    print("--- Aegis Gateway Shutting Down ---")
    if redis_client:
        await redis_client.close()
        print("Redis connection closed.")

app = FastAPI(
    title="Aegis Quantum Citadel",
    description="A zero-trust, predictive security gateway and mobile BFF.",
    version="2.0.0",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(mobile_endpoints.router)
app.include_router(admin.router)

security_shield_router = create_security_shield(settings=settings)

app.include_router(security_shield_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)