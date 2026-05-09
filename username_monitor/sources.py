import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

from .models import Project

LOGGER = logging.getLogger(__name__)


class SourceClient:
    def __init__(self, timeout: int, user_agent: str) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def collect_projects(self) -> List[Project]:
        cap = 80
        coinpaprika = self._coinpaprika_coins()
        random.shuffle(coinpaprika)
        english_words = self._english_words()
        random.shuffle(english_words)
        source_batches = [
            self._dexscreener_latest_profiles()[:cap],
            self._coingecko_trending()[:cap],
            coinpaprika[:cap],
            self._hacker_news_show_hn()[:cap],
            self._defillama_protocols()[:cap],
            self._github_new_repositories()[:cap],
            (self._dexscreener_boosts("latest") + self._dexscreener_boosts("top"))[:cap],
            english_words[:cap],
        ]
        return _dedupe_projects(_round_robin(source_batches))

    def _get_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get_text(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

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

    def _hacker_news_show_hn(self) -> List[Project]:
        url = "https://hn.algolia.com/api/v1/search_by_date?tags=story&query=Show%20HN&hitsPerPage=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News Show HN failed: %s", exc)
            return []

        projects: List[Project] = []
        for item in data.get("hits", []):
            title = item.get("title") or item.get("story_title") or ""
            name = _extract_show_hn_name(title)
            if not name:
                continue
            points = item.get("points") or 0
            comments = item.get("num_comments") or 0
            strength = min(30.0, float(points) / 5 + float(comments) / 10)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News Show HN",
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _defillama_protocols(self) -> List[Project]:
        url = "https://api.llama.fi/protocols"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("DeFiLlama protocols failed: %s", exc)
            return []

        projects: List[Project] = []
        for item in _as_list(data):
            name = item.get("name") or ""
            if not name:
                continue
            tvl = item.get("tvl") or 0
            change = item.get("change_1d") or 0
            strength = min(30.0, max(0.0, float(change)) + min(20.0, float(tvl) / 10_000_000))
            projects.append(
                Project(
                    name=name,
                    symbol=item.get("symbol", ""),
                    source="DeFiLlama Protocols",
                    url=item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _coinpaprika_coins(self) -> List[Project]:
        url = "https://api.coinpaprika.com/v1/coins"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("CoinPaprika coins failed: %s", exc)
            return []

        projects: List[Project] = []
        for item in _as_list(data):
            if not item.get("is_active", False):
                continue
            rank = item.get("rank") or 0
            if not isinstance(rank, int) or rank <= 0 or rank > 200:
                continue
            name = item.get("name") or ""
            symbol = item.get("symbol") or ""
            strength = max(0.0, 25.0 - rank / 10)
            projects.append(
                Project(
                    name=name,
                    symbol=symbol,
                    source="CoinPaprika Coins",
                    url=f"https://coinpaprika.com/coin/{item.get('id')}/" if item.get("id") else None,
                    raw_strength=strength,
                )
            )
        return projects

    def _github_new_repositories(self) -> List[Project]:
        created_after = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
        terms = [
            "crypto",
            "web3",
            "ton",
            "solana",
            "base",
            "telegram bot",
            "ai agent",
            "agent",
            "defi",
            "swap",
            "wallet",
            "chain",
        ]
        projects: List[Project] = []
        for term in terms:
            query = quote(f"{term} created:>={created_after}")
            url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=25"
            try:
                data = self._get_json(url)
            except requests.RequestException as exc:
                LOGGER.warning("GitHub repository search failed for %s: %s", term, exc)
                continue

            for item in data.get("items", []):
                name = item.get("name") or ""
                if not name:
                    continue
                stars = item.get("stargazers_count") or 0
                forks = item.get("forks_count") or 0
                strength = min(25.0, float(stars) * 2 + float(forks))
                projects.append(
                    Project(
                        name=name.replace("-", " ").replace("_", " "),
                        symbol="",
                        source=f"GitHub New Repos: {term}",
                        url=item.get("html_url"),
                        raw_strength=strength,
                    )
                )
        return projects

    def _english_words(self) -> List[Project]:
        url = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("English words failed: %s", exc)
            return []
        words = [w.strip() for w in text.splitlines() if 5 <= len(w.strip()) <= 10 and w.strip().isalpha()]
        return [
            Project(name=word, symbol="", source="English Words", raw_strength=1.0)
            for word in words
        ]

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


def _extract_show_hn_name(title: str) -> str:
    if not title:
        return ""
    title = title.strip()
    title = title.replace("Show HN:", "").replace("Show HN", "", 1).strip(" :-")
    title = re.split(r"\s+[\-\u2013\u2014]\s+", title, maxsplit=1)[0]
    if not title:
        return ""
    for separator in (" - ", ": ", " | "):
        if separator in title:
            title = title.split(separator, 1)[0]
            break
    words = title.split()
    if len(words) > 4:
        title = " ".join(words[:4])
    return title.strip()


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


def _round_robin(batches: List[List[Project]]) -> List[Project]:
    result: List[Project] = []
    max_len = max((len(batch) for batch in batches), default=0)
    for index in range(max_len):
        for batch in batches:
            if index < len(batch):
                result.append(batch[index])
    return result
