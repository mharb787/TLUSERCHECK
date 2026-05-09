import logging
from typing import Any, Dict, Iterable, List, Optional

import requests

from .models import Project

LOGGER = logging.getLogger(__name__)


class SourceClient:
    def __init__(self, timeout: int, user_agent: str) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def collect_projects(self) -> List[Project]:
        projects: List[Project] = []
        projects.extend(self._dexscreener_latest_profiles())
        projects.extend(self._dexscreener_boosts("latest"))
        projects.extend(self._dexscreener_boosts("top"))
        projects.extend(self._coingecko_trending())
        return _dedupe_projects(projects)

    def _get_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _dexscreener_latest_profiles(self) -> List[Project]:
        url = "https://api.dexscreener.com/token-profiles/latest/v1"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("DexScreener profiles failed: %s", exc)
            return []
        return [project for item in _as_list(data) if (project := _project_from_dex_profile(item, "DexScreener Profiles"))]

    def _dexscreener_boosts(self, kind: str) -> List[Project]:
        url = f"https://api.dexscreener.com/token-boosts/{kind}/v1"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("DexScreener %s boosts failed: %s", kind, exc)
            return []
        source = "DexScreener Boosts" if kind == "latest" else "DexScreener Top Boosts"
        return [project for item in _as_list(data) if (project := _project_from_dex_profile(item, source))]

    def _coingecko_trending(self) -> List[Project]:
        url = "https://api.coingecko.com/api/v3/search/trending"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("CoinGecko trending failed: %s", exc)
            return []

        projects: List[Project] = []
        for coin in data.get("coins", []):
            item = coin.get("item", {})
            name = item.get("name")
            if not name:
                continue
            rank = item.get("market_cap_rank")
            trend_score = item.get("score")
            strength = 10.0
            if isinstance(rank, int) and rank > 0:
                strength += max(0, 20 - min(rank, 200) / 10)
            if isinstance(trend_score, (int, float)):
                strength += max(0, 15 - trend_score)
            projects.append(
                Project(
                    name=name,
                    symbol=item.get("symbol", ""),
                    source="CoinGecko Trending",
                    trend_score=trend_score,
                    url=f"https://www.coingecko.com/en/coins/{item.get('id')}" if item.get("id") else None,
                    raw_strength=strength,
                )
            )
        return projects


def _as_list(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _project_from_dex_profile(item: Dict[str, Any], source: str) -> Optional[Project]:
    name = _extract_name_from_dex_item(item)
    if not name:
        return None
    boost = item.get("amount") or item.get("totalAmount") or 0
    strength = float(boost) if isinstance(boost, (int, float)) else 0.0
    return Project(
        name=name,
        symbol="",
        source=source,
        trend_score=strength or None,
        url=item.get("url"),
        raw_strength=min(35.0, strength),
    )


def _extract_name_from_dex_item(item: Dict[str, Any]) -> str:
    description = item.get("description") or ""
    links = item.get("links") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        label = link.get("label") or ""
        if label and label.lower() not in {"website", "twitter", "telegram", "discord"}:
            return label
    if description:
        first_line = description.splitlines()[0]
        words = first_line.split()
        if 1 <= len(words) <= 4:
            return first_line
    url = item.get("url") or ""
    if url:
        return url.rstrip("/").split("/")[-1].replace("-", " ")
    return ""


def _dedupe_projects(projects: Iterable[Project]) -> List[Project]:
    seen = set()
    result = []
    for project in projects:
        key = (project.name.lower(), project.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(project)
    return result
