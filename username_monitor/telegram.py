import logging
from typing import Iterable

import requests

from .models import UsernameOpportunity

LOGGER = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timeout: int, dry_run: bool = False) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout = timeout
        self.dry_run = dry_run

    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_opportunities(self, opportunities: Iterable[UsernameOpportunity]) -> None:
        for opportunity in opportunities:
            self.send_message(format_alert(opportunity))

    def send_message(self, text: str) -> None:
        if self.dry_run or not self.enabled():
            LOGGER.info("Telegram alert skipped/dry-run:\n%s", text)
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()


def format_alert(opportunity: UsernameOpportunity) -> str:
    project = opportunity.project
    liquidity = _money(project.liquidity_usd) if project.liquidity_usd else "N/A"
    volume = _money(project.volume_24h_usd) if project.volume_24h_usd else "N/A"
    lines = [
        "🚨 New Username Opportunity",
        "",
        f"Project: {project.name}",
        f"Source: {project.source}",
        f"Liquidity: {liquidity}",
        f"24h Volume: {volume}",
        f"Telegram Username: @{opportunity.username}",
        f"Fragment Status: {opportunity.fragment_status}",
        f"Score: {opportunity.score}/100",
        f"Why: {opportunity.reason}",
    ]
    if project.url:
        lines.append(f"Source URL: {project.url}")
    return "\n".join(lines)


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"
