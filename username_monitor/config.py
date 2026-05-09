import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    max_alerts_per_run: int = 10
    max_usernames_to_check: int = 500
    min_score: int = 81
    min_project_strength: float = 2.0
    request_timeout: int = 20
    cache_path: str = "data/checked_usernames.json"
    user_agent: str = "telegram-username-monitor/1.0"
    dry_run: bool = False


def load_config() -> Config:
    return Config(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        max_alerts_per_run=_int_env("MAX_ALERTS_PER_RUN", 10),
        max_usernames_to_check=_int_env("MAX_USERNAMES_TO_CHECK", 500),
        min_score=_int_env("MIN_SCORE", 81),
        min_project_strength=float(os.getenv("MIN_PROJECT_STRENGTH", "2.0")),
        request_timeout=_int_env("REQUEST_TIMEOUT", 20),
        cache_path=os.getenv("CACHE_PATH", "data/checked_usernames.json"),
        user_agent=os.getenv("USER_AGENT", "telegram-username-monitor/1.0"),
        dry_run=os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes"},
    )
