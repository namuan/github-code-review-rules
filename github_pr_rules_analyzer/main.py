"""Main FastAPI application for GitHub PR Rules Analyzer."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from github_pr_rules_analyzer.api.routes import router as api_router
from github_pr_rules_analyzer.config import get_settings
from github_pr_rules_analyzer.utils import get_logger
from github_pr_rules_analyzer.utils.database import create_tables, get_database_info

# Configure logging
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> None:
    """Application lifespan events."""
    # Startup
    logger.info("Starting GitHub PR Rules Analyzer API")

    # Initialize database
    logger.info("Creating database tables...")
    create_tables()
    logger.info("Database tables created successfully")

    # Initialize services if needed
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down GitHub PR Rules Analyzer API")
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="GitHub PR Rules Analyzer",
    description="A system that collects, processes, and analyzes GitHub pull request comments to generate coding rules",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")


# Root endpoint with HTML response
@app.get("/", response_class=HTMLResponse)
async def root_html(request: Request) -> HTMLResponse:
    """Root endpoint with HTML response."""
    return templates.TemplateResponse("index.html", {"request": request})


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": "GitHub PR Rules Analyzer",
        "version": "1.0.0",
        "service": "GitHub PR Rules Analyzer",
    }


@app.get("/database-info")
async def database_info() -> dict[str, str]:
    """Database info endpoint."""
    return get_database_info()


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> HTMLResponse | JSONResponse:
    """HTTP exception handler."""
    # Return JSON for API routes, HTML for web routes
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    # For web routes, use appropriate template based on status code
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "error": "Page not found"},
            status_code=404,
        )
    if exc.status_code == 500:
        return templates.TemplateResponse(
            "500.html",
            {"request": request, "error": "Internal server error"},
            status_code=500,
        )
    # Generic error template for other status codes
    return templates.TemplateResponse(
        "500.html",
        {"request": request, "error": f"Error {exc.status_code}: {exc.detail}"},
        status_code=exc.status_code,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> HTMLResponse | JSONResponse:
    """404 error handler for non-HTTP exceptions."""
    # Return JSON for API routes, HTML for web routes
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"},
        )

    return templates.TemplateResponse(
        "404.html",
        {"request": request, "error": "Page not found"},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, _exc: Exception) -> HTMLResponse | JSONResponse:
    """500 error handler."""
    # Return JSON for API routes, HTML for web routes
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return templates.TemplateResponse(
        "500.html",
        {"request": request, "error": "Internal server error"},
        status_code=500,
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
