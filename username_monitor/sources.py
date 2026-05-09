import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

from .models import Project
from .pagination import PaginationState

LOGGER = logging.getLogger(__name__)

_GITHUB_TRENDING_PERIODS = ["daily", "weekly", "monthly"]


class SourceClient:
    def __init__(self, timeout: int, user_agent: str) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    def collect_projects(self, pagination_state: PaginationState) -> List[Project]:
        all_projects: List[Project] = []

        # HackerNews Show HN with pagination
        hn_show_page = pagination_state.get("hn_show_hn", "page", 0)
        hn_show_results = self._hacker_news_show_hn(hn_show_page)
        if hn_show_results:
            pagination_state.set("hn_show_hn", "page", hn_show_page + 1)
        else:
            pagination_state.set("hn_show_hn", "page", 0)
        all_projects.extend(hn_show_results)

        # HackerNews top stories with pagination
        hn_top_page = pagination_state.get("hn_top", "page", 0)
        hn_top_results = self._hacker_news_top(hn_top_page)
        if hn_top_results:
            pagination_state.set("hn_top", "page", hn_top_page + 1)
        else:
            pagination_state.set("hn_top", "page", 0)
        all_projects.extend(hn_top_results)

        # GitHub trending with period cycling
        period_index = pagination_state.get("github_trending", "period_index", 0)
        period = _GITHUB_TRENDING_PERIODS[period_index % len(_GITHUB_TRENDING_PERIODS)]
        all_projects.extend(self._github_trending(period))
        pagination_state.set("github_trending", "period_index", (period_index + 1) % len(_GITHUB_TRENDING_PERIODS))

        # GitHub new repos with days_offset
        days_offset = pagination_state.get("github_new_repos", "days_offset", 0)
        all_projects.extend(self._github_new_repos(days_offset))
        pagination_state.set("github_new_repos", "days_offset", days_offset + 14)

        # Reddit posts with after cursor per subreddit
        for subreddit in ("startups", "SideProject", "entrepreneur", "MachineLearning", "technology", "artificial"):
            after_cursor = pagination_state.get(f"reddit_{subreddit}", "after", None)
            reddit_results, new_after = self._reddit_posts(subreddit, after_cursor)
            all_projects.extend(reddit_results)
            if new_after:
                pagination_state.set(f"reddit_{subreddit}", "after", new_after)
            else:
                pagination_state.set(f"reddit_{subreddit}", "after", None)

        # Product Hunt RSS
        all_projects.extend(self._producthunt_rss())

        # TechCrunch RSS
        all_projects.extend(self._techcrunch_rss())

        # VentureBeat RSS
        all_projects.extend(self._venturebeat_rss())

        # Wikipedia trending with days_offset
        wiki_days_offset = pagination_state.get("wikipedia_trending", "days_offset", 1)
        all_projects.extend(self._wikipedia_trending(wiki_days_offset))
        pagination_state.set("wikipedia_trending", "days_offset", wiki_days_offset + 1)

        # App Store top apps
        all_projects.extend(self._appstore_top())

        # YC companies
        all_projects.extend(self._ycombinator_companies())

        return _dedupe_projects(all_projects)

    def _get_json(self, url: str) -> Any:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _get_text(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _hacker_news_show_hn(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=story&query=Show%20HN&hitsPerPage=100&page={page}"
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

    def _hacker_news_top(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=points>100&hitsPerPage=100&page={page}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News top failed: %s", exc)
            return []

        projects: List[Project] = []
        for item in data.get("hits", []):
            title = item.get("title") or item.get("story_title") or ""
            if not title:
                continue
            name = re.split(r"\s*[-–|:]\s*", title, maxsplit=1)[0].strip()
            words = name.split()
            if len(words) > 5:
                name = " ".join(words[:5])
            if not name:
                continue
            points = item.get("points") or 0
            comments = item.get("num_comments") or 0
            strength = min(30.0, float(points) / 10 + float(comments) / 20)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News Top",
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _github_trending(self, period: str) -> List[Project]:
        url = f"https://api.github.com/search/repositories?q=created:>{_days_ago(7)}&sort=stars&order=desc&per_page=100"
        if period == "weekly":
            url = f"https://api.github.com/search/repositories?q=created:>{_days_ago(30)}&sort=stars&order=desc&per_page=100"
        elif period == "monthly":
            url = f"https://api.github.com/search/repositories?q=created:>{_days_ago(90)}&sort=stars&order=desc&per_page=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("GitHub trending (%s) failed: %s", period, exc)
            return []
        projects = []
        for item in data.get("items", []):
            name = item.get("name") or ""
            if not name:
                continue
            stars = item.get("stargazers_count") or 0
            strength = min(30.0, float(stars) / 100)
            projects.append(Project(
                name=name.replace("-", " ").replace("_", " "),
                symbol="",
                source=f"GitHub Trending ({period})",
                url=item.get("html_url"),
                raw_strength=strength,
            ))
        return projects

    def _github_new_repos(self, days_offset: int) -> List[Project]:
        start = _days_ago(days_offset + 14)
        end = _days_ago(days_offset)
        query = quote(f"created:{start}..{end} stars:>5")
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("GitHub new repos (offset=%s) failed: %s", days_offset, exc)
            return []
        projects = []
        for item in data.get("items", []):
            name = item.get("name") or ""
            if not name:
                continue
            stars = item.get("stargazers_count") or 0
            forks = item.get("forks_count") or 0
            strength = min(25.0, float(stars) * 2 + float(forks))
            projects.append(Project(
                name=name.replace("-", " ").replace("_", " "),
                symbol="",
                source="GitHub New Repos",
                url=item.get("html_url"),
                raw_strength=strength,
            ))
        return projects

    def _reddit_posts(self, subreddit: str, after_cursor: Optional[str]) -> tuple:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=100"
        if after_cursor:
            url += f"&after={after_cursor}"
        headers = {"Accept": "application/json", "User-Agent": self.session.headers.get("User-Agent", "bot")}
        try:
            resp = self.session.get(url, timeout=self.timeout, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            LOGGER.warning("Reddit r/%s failed: %s", subreddit, exc)
            return [], None

        projects = []
        new_after = data.get("data", {}).get("after")
        for post in data.get("data", {}).get("children", []):
            title = post.get("data", {}).get("title") or ""
            name = re.split(r"\s*[-–|:]\s*", title, maxsplit=1)[0].strip()
            score = post.get("data", {}).get("score") or 0
            strength = min(20.0, float(score) / 10)
            if name:
                projects.append(Project(name=name, symbol="", source=f"Reddit r/{subreddit}", raw_strength=strength))
        return projects, new_after

    def _producthunt_rss(self) -> List[Project]:
        url = "https://www.producthunt.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Product Hunt RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Product Hunt", base_strength=5.0)

    def _techcrunch_rss(self) -> List[Project]:
        url = "https://techcrunch.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("TechCrunch RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "TechCrunch", base_strength=4.0)

    def _venturebeat_rss(self) -> List[Project]:
        url = "https://venturebeat.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("VentureBeat RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "VentureBeat", base_strength=4.0)

    def _wikipedia_trending(self, days_offset: int) -> List[Project]:
        target_date = datetime.now(timezone.utc) - timedelta(days=days_offset)
        year = target_date.strftime("%Y")
        month = target_date.strftime("%m")
        day = target_date.strftime("%d")
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/{year}/{month}/{day}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Wikipedia trending (offset=%s) failed: %s", days_offset, exc)
            return []
        projects = []
        articles = []
        try:
            articles = data["items"][0]["articles"]
        except (KeyError, IndexError, TypeError):
            pass
        for article in articles[:100]:
            name = article.get("article", "").replace("_", " ")
            # Skip meta pages
            if ":" in name or name.startswith("Main_Page") or name == "Main Page":
                continue
            views = article.get("views") or 0
            strength = min(20.0, float(views) / 100000)
            projects.append(Project(name=name, symbol="", source="Wikipedia Trending", raw_strength=strength))
        return projects

    def _appstore_top(self) -> List[Project]:
        url = "https://rss.applemarketingtools.com/api/v2/us/apps/top-free/100/apps.json"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("App Store top apps failed: %s", exc)
            return []
        projects = []
        results = []
        try:
            results = data["feed"]["results"]
        except (KeyError, TypeError):
            pass
        for i, item in enumerate(results):
            name = item.get("name") or ""
            if not name:
                continue
            # Higher rank = lower strength (rank 1 is strongest)
            strength = max(1.0, 20.0 - i * 0.2)
            projects.append(Project(name=name, symbol="", source="App Store Top", raw_strength=strength))
        return projects

    def _ycombinator_companies(self) -> List[Project]:
        url = "https://hn.algolia.com/api/v1/search?query=&tags=story&numericFilters=points>100&hitsPerPage=100&page=0"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("YC companies (HN Algolia) failed: %s", exc)
            return []
        projects = []
        for item in data.get("hits", []):
            title = item.get("title") or ""
            # Look for YC-style: "Launch YC: CompanyName" or "YC S23: CompanyName"
            yc_match = re.search(r"(?:Launch\s+YC|YC\s+[A-Z]\d+)\s*[:\-]\s*(.+)", title, re.IGNORECASE)
            if yc_match:
                name = yc_match.group(1).strip()
            else:
                name = re.split(r"\s*[-–|:]\s*", title, maxsplit=1)[0].strip()
            words = name.split()
            if len(words) > 5:
                name = " ".join(words[:5])
            if not name:
                continue
            points = item.get("points") or 0
            strength = min(25.0, float(points) / 10)
            projects.append(Project(name=name, symbol="", source="YC Companies", raw_strength=strength))
        return projects


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


def _parse_rss_titles(text: str, source: str, base_strength: float = 5.0) -> List[Project]:
    projects = []
    # Try CDATA first
    names = re.findall(r"<title><!\[CDATA\[([^\]]+)\]\]></title>", text)
    if not names:
        # Try plain XML titles
        try:
            root = ET.fromstring(text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            names = []
            for elem in root.iter():
                if elem.tag in ("title", "{http://www.w3.org/2005/Atom}title"):
                    if elem.text:
                        names.append(elem.text.strip())
        except ET.ParseError:
            names = re.findall(r"<title>([^<]{3,80})</title>", text)

    # Skip first title (usually the feed title)
    for name in names[1:]:
        # Extract company/product name: take the part before dash, pipe, colon
        name = re.sub(r"\s*[-–|]\s*.*$", "", name).strip()
        name = re.sub(r":\s*.*$", "", name).strip()
        if name and len(name) >= 2:
            projects.append(Project(name=name, symbol="", source=source, raw_strength=base_strength))
    return projects


def _extract_show_hn_name(title: str) -> str:
    if not title:
        return ""
    title = title.strip()
    title = title.replace("Show HN:", "").replace("Show HN", "", 1).strip(" :-")
    title = re.split(r"\s+[\-–—]\s+", title, maxsplit=1)[0]
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
