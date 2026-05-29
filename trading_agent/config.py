"""Runtime configuration for the Normies Intelligence Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Configuration loaded from environment variables and CLI defaults."""

    normies_base_url: str = "https://api.normies.art"
    database_path: Path = Path("data/trading_agent.sqlite3")
    cache_dir: Path = Path(".cache/normies")
    request_timeout_seconds: float = 10.0
    requests_per_minute: int = 55
    user_agent: str = "Trading-Agent/0.1 NormiesIntelligenceAgent"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            normies_base_url=os.getenv("NORMIES_BASE_URL", cls.normies_base_url).rstrip("/"),
            database_path=Path(os.getenv("TRADING_AGENT_DB", str(cls.database_path))),
            cache_dir=Path(os.getenv("NORMIES_CACHE_DIR", str(cls.cache_dir))),
            request_timeout_seconds=float(
                os.getenv("NORMIES_TIMEOUT_SECONDS", str(cls.request_timeout_seconds))
            ),
            requests_per_minute=int(os.getenv("NORMIES_REQUESTS_PER_MINUTE", str(cls.requests_per_minute))),
            user_agent=os.getenv("NORMIES_USER_AGENT", cls.user_agent),
        )


def ensure_runtime_dirs(settings: Settings) -> None:
    """Create runtime directories for the SQLite database and HTTP cache."""

    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
