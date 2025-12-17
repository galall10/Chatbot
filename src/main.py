"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings
from src.core.logging import setup_logging, get_logger
from src.api.chat import router as chat_router
from src.memory.redis_memory import memory
from src.schemas.chat import HealthResponse

# Initialize logging
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    This manages Redis connections and other resources.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    # Connect to Redis
    await memory.connect()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await memory.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade LLM chatbot service with streaming responses",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat_router, tags=["chat"])


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        HealthResponse: Service health status
    """
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment
    )


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
