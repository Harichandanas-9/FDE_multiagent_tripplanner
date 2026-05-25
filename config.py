"""Central settings loaded from .env."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


@dataclass
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    google_places_api_key: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    project_root: Path = ROOT
    outputs_dir: Path = ROOT / "outputs"
    memory_dir: Path = ROOT / "memory" / "vector_store"

    def has_openai(self): return bool(self.openai_api_key and self.openai_api_key.startswith("sk-"))
    def has_weather(self): return bool(self.openweather_api_key)


settings = Settings()
settings.outputs_dir.mkdir(parents=True, exist_ok=True)
settings.memory_dir.mkdir(parents=True, exist_ok=True)
