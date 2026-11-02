"""
Centralized configuration loaded from .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # ── LLM ───────────────────────────────────────────────
    llm_provider: str = Field(default="gemini", description="LLM provider: gemini")
    llm_api_key: str = Field(default="", description="Gemini API key")
    llm_model: str = Field(default="gemini-3.6-flash", description="Gemini model name")

    # ── API ───────────────────────────────────────────────
    api_key: str = Field(default="change-me-to-a-random-secret", description="API key for local server auth")
    api_host: str = Field(default="127.0.0.1", description="Bind host (localhost only)")
    api_port: int = Field(default=8000, description="Server port")

    # ── WhatsApp ──────────────────────────────────────────
    whatsapp_profile_dir: str = Field(
        default="storage/whatsapp_profile",
        description="Directory for Playwright persistent browser profile",
    )
    whatsapp_headless: bool = Field(
        default=False,
        description="Run browser in headless mode (must be False for QR scan)",
    )

    # ── Logging ───────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Logging level")

    # ── Database ──────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///storage/agent.db",
        description="SQLite database URL",
    )
    chroma_db_dir: str = Field(
        default="storage/chroma_db",
        description="Directory for ChromaDB vector database",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def profile_path(self) -> Path:
        """Resolved absolute path to the browser profile directory."""
        return Path(self.whatsapp_profile_dir).resolve()

    @property
    def db_path(self) -> str:
        """Extract the raw file path from the database URL."""
        return self.database_url.replace("sqlite+aiosqlite:///", "")


# Global singleton — import this everywhere
settings = Settings()
