from functools import lru_cache
from pathlib import Path
from typing import List, Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - compatibility with older local environments.
    from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Detective Agent Backend"
    api_prefix: str = "/api/v1"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    ai_service_base_url: Optional[str] = None
    ai_timeout_seconds: float = 2.0
    ai_max_retries: int = 1
    debug_tools_enabled: bool = False
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_prefix = "BE_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
