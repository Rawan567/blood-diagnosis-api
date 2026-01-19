"""
Entry point for Railway deployment
Just imports and re-exports the app from app.main
"""
from app.main import app

__all__ = ["app"]