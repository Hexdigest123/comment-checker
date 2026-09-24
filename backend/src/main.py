"""
Comment Checker Backend - FastAPI Application
Main entry point for the FastAPI application
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db.session import init_db, close_db
from .api import (
    auth,
    users,
    comments,
    classification,
    dashboard,
    accounts,
    clusters,
    ai,
    imports,
    admin,
)
from .services.first_admin import create_first_admin_on_startup
from .services.worker import worker

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(
        f"Environment: {'production' if settings.production else 'development'}"
    )
    await init_db()
    logger.info("Database initialized")

    await create_first_admin_on_startup()
    logger.info("First admin check completed")

    # Start the classification worker (job queue for PENDING comments)
    if settings.worker_enabled:
        worker.start()
        logger.info("Classification worker started")
    else:
        logger.info("Classification worker disabled (WORKER_ENABLED=false)")

    logger.info(f"Server running on http://{settings.host}:{settings.port}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await worker.stop()
    logger.info("Classification worker stopped")
    await close_db()
    logger.info("Database connections closed")
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Comment Checker API - Classify comments for hate speech and harmful content",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    debug=settings.debug,
)

# Add CORS middleware - OWASP: Restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Security middleware - OWASP recommendations
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # HSTS
    response.headers["Strict-Transport-Security"] = (
        f"max-age={settings.hsts_max_age}; "
        f"includeSubDomains={'true' if settings.hsts_include_subdomains else 'false'}; "
        f"preload={'true' if settings.hsts_preload else 'false'}"
    )

    # X-Frame-Options
    response.headers["X-Frame-Options"] = settings.frame_options

    # X-Content-Type-Options
    response.headers["X-Content-Type-Options"] = settings.x_content_type_options

    # X-XSS-Protection
    response.headers["X-XSS-Protection"] = settings.x_xss_protection

    # Content Security Policy
    csp_directives = [
        f"default-src {settings.csp_default_src}",
        f"script-src {settings.csp_script_src}",
        f"style-src {settings.csp_style_src}",
        f"img-src {settings.csp_img_src}",
        f"font-src {settings.csp_font_src}",
        f"connect-src {settings.csp_connect_src}",
    ]
    response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    # Cache control for API responses
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"] = "no-cache"

    return response

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(comments.router, prefix="/api/v1/comments", tags=["Comments"])
app.include_router(classification.router, prefix="/api/v1/classifications", tags=["Classifications"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(accounts.router, prefix="/api/v1/external-accounts", tags=["External Accounts"])
app.include_router(clusters.router, prefix="/api/v1/clusters", tags=["Clusters"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Assistant"])
app.include_router(imports.router, prefix="/api/v1/import", tags=["Import"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "worker": {
            "enabled": settings.worker_enabled,
            "running": worker.is_running,
            "processed": worker.processed,
            "failed": worker.failed,
        },
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/api/docs",
    }

# Mount static files (for serving frontend in production)
# In development, frontend runs separately on port 3000
if settings.production:
    app.mount(
        "/", StaticFiles(directory="../frontend/dist", html=True), name="frontend"
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
