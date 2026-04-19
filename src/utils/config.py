"""
Configuration loader — reads .env + YAML configs into typed Pydantic models.
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — primary
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # LLM — cheap
    llm_cheap_provider: str = "anthropic"
    llm_cheap_model: str = "claude-haiku-4-5-20251001"

    # News
    newsapi_key: str = ""

    # Database
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR}/pilot.db"

    # Email — Resend
    resend_api_key: str = ""
    email_to: str = ""
    email_from: str = "pilot@resend.dev"

    # Email — SMTP fallback
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Schedule
    pipeline_hour: int = 5
    pipeline_minute: int = 0
    timezone: str = "UTC"

    # Pipeline
    log_level: str = "INFO"
    posts_per_run: int = 7


def _load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def load_sources() -> dict:
    return _load_yaml("sources.yaml")

def load_persona() -> dict:
    return _load_yaml("persona_dna.yaml")

def load_angles() -> dict:
    return _load_yaml("angles.yaml")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()