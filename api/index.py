"""Vercel Python entrypoint for the public demo API (mock mode, in-memory stores)."""

from apps.api.main import app

__all__ = ["app"]
