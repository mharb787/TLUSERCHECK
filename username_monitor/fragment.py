import logging
import re
from dataclasses import dataclass
from typing import Optional

import requests

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FragmentResult:
    username: str
    status: str
    url: str

    @property
    def is_available(self) -> bool:
        return self.status == "Unavailable"


class FragmentClient:
    def __init__(self, timeout: int, user_agent: str, bot_token: Optional[str] = None) -> None:
        self.timeout = timeout
        self.bot_token = bot_token
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml",
            }
        )

    def check_username(self, username: str) -> FragmentResult:
        url = f"https://fragment.com/username/{username}"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            LOGGER.warning("Fragment check failed for @%s: %s", username, exc)
            return FragmentResult(username=username, status="Unknown", url=url)

        if response.status_code == 404:
            return FragmentResult(username=username, status="No Fragment listing", url=url)
        if response.status_code >= 400:
            return FragmentResult(username=username, status=f"HTTP {response.status_code}", url=url)

        text = response.text.lower()

        if "unavailable" in text:
            if self._is_registered_on_telegram(username):
                return FragmentResult(username=username, status="Taken in Telegram", url=url)
            return FragmentResult(username=username, status="Unavailable", url=url)
        if "on auction" in text or "place bid" in text:
            return FragmentResult(username=username, status="Auction", url=url)
        if "sold" in text or "owner" in text:
            return FragmentResult(username=username, status="Taken", url=url)
        if re.search(r"username\s+is\s+available|not\s+found", text):
            return FragmentResult(username=username, status="Available", url=url)
        return FragmentResult(username=username, status="Unknown", url=url)

    def _is_registered_on_telegram(self, username: str) -> bool:
        if not self.bot_token:
            return False
        try:
            api_url = f"https://api.telegram.org/bot{self.bot_token}/getChat"
            response = self.session.post(
                api_url,
                json={"chat_id": f"@{username}"},
                timeout=self.timeout,
            )
            data = response.json()
            registered = data.get("ok", False)
            LOGGER.info("Telegram registration check @%s: %s", username, "taken" if registered else "free")
            return registered
        except requests.RequestException as exc:
            LOGGER.warning("Telegram getChat failed for @%s: %s", username, exc)
            return False
