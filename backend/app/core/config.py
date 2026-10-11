"""
AegisAI Application Configuration Shim.

Directs callers to the canonical settings module at `app.core.config.settings`.
"""

from app.core.config.settings import AppSettings, settings

__all__ = ["AppSettings", "settings"]
