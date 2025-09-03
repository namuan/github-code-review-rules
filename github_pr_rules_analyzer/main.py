"""Main FastAPI application for GitHub PR Rules Analyzer."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from github_pr_rules_analyzer.api.routes import router as api_router
from github_pr_rules_analyzer.config import get_settings
from github_pr_rules_analyzer.utils import get_logger
from github_pr_rules_analyzer.utils.database import create_tables

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
    return {"status": "healthy", "service": "GitHub PR Rules Analyzer"}


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, _exc: Exception) -> HTMLResponse:
    """404 error handler."""
    return templates.TemplateResponse(
        "404.html",
        {"request": request, "error": "Page not found"},
        status_code=404,
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, _exc: Exception) -> HTMLResponse:
    """500 error handler."""
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
