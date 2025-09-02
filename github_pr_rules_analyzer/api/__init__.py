"""API routes and endpoints."""

from fastapi import APIRouter

api_router = APIRouter()

# Import and include API modules
# from . import collector, analysis, presentation

__all__ = ["api_router"]
