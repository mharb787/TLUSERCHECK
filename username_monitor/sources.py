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

_REDDIT_SUBREDDITS = [
    # Startups & Business
    "startups", "SideProject", "entrepreneur", "Entrepreneur", "solofounder",
    "buildinpublic", "microsaas", "saas", "techstartups", "smallbusiness",
    "passive_income", "ecommerce", "b2b", "consulting", "freelance",
    "growthhacking", "vc", "venturecapital", "angelinvesting", "YCombinator",
    "nocode", "lowcode", "buyabusiness", "acquisitions", "indiebiz",
    # Tech & Programming
    "programming", "webdev", "javascript", "python", "golang", "rust",
    "typescript", "cpp", "java", "csharp", "swift", "kotlin", "ruby",
    "haskell", "elixir", "scala", "clojure", "lua", "zig", "nim",
    "androiddev", "iphone", "FlutterDev", "reactnative", "unitydev",
    "gamedev", "indiegaming", "unrealengine", "GameDevelopment",
    "MachineLearning", "deeplearning", "artificial", "singularity",
    "LocalLLaMA", "StableDiffusion", "ChatGPT", "OpenAI", "AIAssistants",
    "datascience", "learnmachinelearning", "computervision", "mlops",
    "devops", "kubernetes", "docker", "terraform", "serverless",
    "netsec", "cybersecurity", "hacking", "ReverseEngineering", "netsec",
    "linux", "opensource", "selfhosted", "sysadmin", "homelab",
    "vim", "emacs", "commandline", "bash", "PowerShell",
    # Tech News & Products
    "technology", "Futurology", "InternetIsBeautiful", "webapps",
    "apps", "software", "coding", "productivity", "digitalnomad",
    "remotework", "fintech", "biotech", "healthtech", "edtech",
    "robotics", "iot", "blockchain", "web3", "CryptoTechnology",
    # Design & Product
    "UI_Design", "UXDesign", "graphic_design", "web_design",
    "ProductManagement", "product_design", "userexperience",
    # Marketing & Growth
    "SEO", "content_marketing", "affiliatemarketing", "dropshipping",
    "digitalmarketing", "socialmedia", "PPC",
    # Cloud & Infrastructure
    "aws", "googlecloud", "AZURE", "DatabaseHelp", "PostgreSQL",
    "redis", "mongodb", "elasticsearch",
]

_GITHUB_TOPICS = [
    # AI & ML
    "ai", "ml", "llm", "machine-learning", "deep-learning", "neural-network",
    "computer-vision", "nlp", "speech-recognition", "reinforcement-learning",
    "langchain", "agents", "rag", "vector-database", "embedding", "chatbot",
    "stable-diffusion", "generative-ai", "transformers", "fine-tuning",
    # Web & Backend
    "saas", "api", "rest-api", "graphql", "grpc", "microservices",
    "web", "nextjs", "react", "vue", "svelte", "nuxtjs", "astro",
    "fastapi", "django", "flask", "express", "nestjs", "laravel",
    "websocket", "realtime", "webhook",
    # DevTools & Infrastructure
    "cli", "devtools", "automation", "workflow", "pipeline", "ci-cd",
    "docker", "kubernetes", "terraform", "ansible", "monitoring", "observability",
    "logging", "tracing", "dashboard", "analytics", "scraper", "crawler",
    # Mobile & Desktop
    "mobile", "flutter", "react-native", "ios", "android", "electron",
    "tauri", "macos", "cross-platform",
    # Security
    "security", "cryptography", "authentication", "oauth", "jwt",
    "penetration-testing", "vulnerability", "privacy", "zero-trust",
    # Data & Database
    "database", "postgresql", "redis", "mongodb", "sqlite", "timeseries",
    "data-engineering", "etl", "streaming", "kafka", "spark",
    # Languages & Runtimes
    "rust", "typescript", "swift", "kotlin", "golang", "zig", "wasm",
    "deno", "bun", "nodejs",
    # Blockchain & Web3
    "blockchain", "web3", "defi", "smart-contract", "solidity", "nft",
    # Gaming
    "gaming", "game-engine", "unity", "godot", "game-development",
    # Other
    "productivity", "finance", "education", "healthtech", "open-source",
    "self-hosted", "homelab", "assistant", "extension", "plugin",
]

_GITHUB_LANGUAGES = [
    "python", "javascript", "typescript", "rust", "go", "swift",
    "kotlin", "cpp", "java", "ruby", "c", "csharp", "php",
    "scala", "elixir", "haskell", "lua", "zig", "dart", "julia",
]


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

        # HackerNews Ask HN with pagination
        hn_ask_page = pagination_state.get("hn_ask", "page", 0)
        hn_ask_results = self._hacker_news_ask(hn_ask_page)
        if hn_ask_results:
            pagination_state.set("hn_ask", "page", hn_ask_page + 1)
        else:
            pagination_state.set("hn_ask", "page", 0)
        all_projects.extend(hn_ask_results)

        # HackerNews new stories with pagination
        hn_new_page = pagination_state.get("hn_new", "page", 0)
        hn_new_results = self._hacker_news_new(hn_new_page)
        if hn_new_results:
            pagination_state.set("hn_new", "page", hn_new_page + 1)
        else:
            pagination_state.set("hn_new", "page", 0)
        all_projects.extend(hn_new_results)

        # GitHub trending with period cycling
        period_index = pagination_state.get("github_trending", "period_index", 0)
        period = _GITHUB_TRENDING_PERIODS[period_index % len(_GITHUB_TRENDING_PERIODS)]
        all_projects.extend(self._github_trending(period))
        pagination_state.set("github_trending", "period_index", (period_index + 1) % len(_GITHUB_TRENDING_PERIODS))

        # GitHub new repos with days_offset
        days_offset = pagination_state.get("github_new_repos", "days_offset", 0)
        all_projects.extend(self._github_new_repos(days_offset))
        pagination_state.set("github_new_repos", "days_offset", days_offset + 14)

        # GitHub topic repos with days_offset per topic
        for topic in _GITHUB_TOPICS:
            state_key = f"github_topic_{topic}"
            topic_days_offset = pagination_state.get(state_key, "days_offset", 0)
            all_projects.extend(self._github_topic_repos(topic, topic_days_offset))
            pagination_state.set(state_key, "days_offset", topic_days_offset + 14)

        # Reddit posts with after cursor per subreddit (35 subreddits)
        for subreddit in _REDDIT_SUBREDDITS:
            after_cursor = pagination_state.get(f"reddit_{subreddit}", "after", None)
            reddit_results, new_after = self._reddit_posts(subreddit, after_cursor)
            all_projects.extend(reddit_results)
            if new_after:
                pagination_state.set(f"reddit_{subreddit}", "after", new_after)
            else:
                pagination_state.set(f"reddit_{subreddit}", "after", None)

        # Product Hunt RSS (confirmed working)
        all_projects.extend(self._producthunt_rss())

        # Lobsters RSS (confirmed working)
        all_projects.extend(self._lobsters_rss())

        # Wikipedia trending
        wiki_days_offset = pagination_state.get("wikipedia_trending", "days_offset", 1)
        all_projects.extend(self._wikipedia_trending(wiki_days_offset))
        pagination_state.set("wikipedia_trending", "days_offset", wiki_days_offset + 1)

        # App Store top apps
        all_projects.extend(self._appstore_top())

        # YC companies
        all_projects.extend(self._ycombinator_companies())

        # npm trending packages
        npm_offset = pagination_state.get("npm_packages", "offset", 0)
        all_projects.extend(self._npm_trending(npm_offset))
        pagination_state.set("npm_packages", "offset", npm_offset + 100)

        # PyPI top packages
        pypi_offset = pagination_state.get("pypi_packages", "pypi_offset", 0)
        all_projects.extend(self._pypi_top(pypi_offset))
        pagination_state.set("pypi_packages", "pypi_offset", pypi_offset + 100)

        # GitHub language trending
        for language in _GITHUB_LANGUAGES:
            state_key = f"github_lang_{language}"
            lang_days_offset = pagination_state.get(state_key, "days_offset", 0)
            all_projects.extend(self._github_language_trending(language, lang_days_offset))
            pagination_state.set(state_key, "days_offset", lang_days_offset + 7)

        # HackerNews jobs
        hn_jobs_page = pagination_state.get("hn_jobs", "page", 0)
        hn_jobs_results = self._hacker_news_jobs(hn_jobs_page)
        if hn_jobs_results:
            pagination_state.set("hn_jobs", "page", hn_jobs_page + 1)
        else:
            pagination_state.set("hn_jobs", "page", 0)
        all_projects.extend(hn_jobs_results)

        # HackerNews who is hiring
        hn_hiring_page = pagination_state.get("hn_hiring", "page", 0)
        hn_hiring_results = self._hacker_news_who_is_hiring(hn_hiring_page)
        if hn_hiring_results:
            pagination_state.set("hn_hiring", "page", hn_hiring_page + 1)
        else:
            pagination_state.set("hn_hiring", "page", 0)
        all_projects.extend(hn_hiring_results)

        # Crates.io (Rust packages)
        cratesio_offset = pagination_state.get("cratesio", "offset", 0)
        all_projects.extend(self._cratesio_top(cratesio_offset))
        pagination_state.set("cratesio", "offset", cratesio_offset + 100)

        # NuGet (.NET packages)
        nuget_offset = pagination_state.get("nuget", "offset", 0)
        all_projects.extend(self._nuget_top(nuget_offset))
        pagination_state.set("nuget", "offset", nuget_offset + 100)

        # RubyGems
        rubygems_offset = pagination_state.get("rubygems", "offset", 0)
        all_projects.extend(self._rubygems_top(rubygems_offset))
        pagination_state.set("rubygems", "offset", rubygems_offset + 30)

        # === HIGH-VOLUME NEW SOURCES ===

        # SEC EDGAR — US company names + tickers (13,000+ entries)
        edgar_offset = pagination_state.get("sec_edgar", "offset", 0)
        all_projects.extend(self._sec_edgar_companies(edgar_offset))
        pagination_state.set("sec_edgar", "offset", edgar_offset + 500)

        # English 4-letter word list (ENABLE dictionary ~3,500 words)
        if not pagination_state.get("enable_words", "done", False):
            words = self._english_words()
            all_projects.extend(words)
            if words:
                pagination_state.set("enable_words", "done", True)

        # NASDAQ + NYSE stock tickers
        nasdaq_offset = pagination_state.get("nasdaq_tickers", "offset", 0)
        all_projects.extend(self._stock_tickers(nasdaq_offset))
        pagination_state.set("nasdaq_tickers", "offset", nasdaq_offset + 500)

        # GeoNames: 4-letter city names worldwide
        if not pagination_state.get("geonames", "done", False):
            cities = self._geonames_cities()
            all_projects.extend(cities)
            if cities:
                pagination_state.set("geonames", "done", True)

        # Packagist (PHP packages)
        packagist_page = pagination_state.get("packagist", "page", 1)
        all_projects.extend(self._packagist_packages(packagist_page))
        pagination_state.set("packagist", "page", packagist_page + 1)

        # Go module proxy trending
        go_offset = pagination_state.get("go_modules", "offset", 0)
        all_projects.extend(self._go_modules(go_offset))
        pagination_state.set("go_modules", "offset", go_offset + 100)

        return _dedupe_projects(all_projects)

    def _sec_edgar_companies(self, offset: int) -> List[Project]:
        url = "https://www.sec.gov/files/company_tickers.json"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("SEC EDGAR failed: %s", exc)
            return []
        entries = list(data.values())
        page = entries[offset: offset + 500]
        projects = []
        for entry in page:
            name = (entry.get("title") or "").strip()
            ticker = (entry.get("ticker") or "").strip().lower()
            if name:
                projects.append(Project(name=name, symbol=ticker, source="SEC EDGAR", raw_strength=5.0))
            if ticker and ticker.isalpha():
                projects.append(Project(name=ticker, symbol=ticker, source="SEC EDGAR Ticker", raw_strength=7.0))
        return projects

    def _english_words(self) -> List[Project]:
        url = "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("English word list failed: %s", exc)
            return []
        words = [w.strip().lower() for w in text.splitlines() if w.strip().isalpha()]
        return [Project(name=w, symbol="", source="English Dictionary", raw_strength=8.0) for w in words]

    def _stock_tickers(self, offset: int) -> List[Project]:
        # Fetch full NASDAQ + NYSE ticker list via SEC EDGAR exchange data
        urls = [
            "https://www.sec.gov/files/company_tickers_exchange.json",
        ]
        projects = []
        for url in urls:
            try:
                data = self._get_json(url)
            except requests.RequestException as exc:
                LOGGER.warning("Stock tickers failed (%s): %s", url, exc)
                continue
            fields = data.get("fields", [])
            rows = data.get("data", [])
            try:
                ticker_idx = fields.index("ticker")
                name_idx = fields.index("name")
            except ValueError:
                continue
            page = rows[offset: offset + 500]
            for row in page:
                ticker = str(row[ticker_idx]).strip().lower()
                name = str(row[name_idx]).strip()
                if ticker and ticker.isalpha():
                    projects.append(Project(name=ticker, symbol=ticker, source="Stock Ticker", raw_strength=7.0))
                if name:
                    projects.append(Project(name=name, symbol=ticker, source="Stock Company", raw_strength=5.0))
        return projects

    def _geonames_cities(self) -> List[Project]:
        # GeoNames top 1000 cities (CC BY license, no auth needed for this endpoint)
        url = "https://raw.githubusercontent.com/datasets/world-cities/master/data/world-cities.csv"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("GeoNames cities failed: %s", exc)
            return []
        projects = []
        for line in text.splitlines()[1:]:
            parts = line.split(",")
            if not parts:
                continue
            city = parts[0].strip().strip('"').lower()
            if city.isalpha():
                projects.append(Project(name=city, symbol="", source="City Names", raw_strength=6.0))
        return projects

    def _packagist_packages(self, page: int) -> List[Project]:
        url = f"https://packagist.org/search.json?q=&page={page}&per_page=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Packagist failed: %s", exc)
            return []
        projects = []
        for pkg in data.get("results", []):
            name = pkg.get("name") or ""
            # Strip vendor prefix: vendor/package → package
            short = name.split("/")[-1] if "/" in name else name
            display = short.replace("-", " ").replace("_", " ")
            if display:
                projects.append(Project(name=display, symbol="", source="Packagist", raw_strength=3.0))
        return projects

    def _go_modules(self, offset: int) -> List[Project]:
        url = f"https://goproxy.io/stats/top?limit=100&offset={offset}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Go modules failed: %s", exc)
            return []
        projects = []
        for item in data if isinstance(data, list) else data.get("results", []):
            path = (item.get("module") or item.get("path") or "").strip()
            if not path:
                continue
            # Extract last segment: github.com/user/repo → repo
            name = path.rstrip("/").split("/")[-1]
            display = name.replace("-", " ").replace("_", " ").replace(".", " ")
            if display:
                projects.append(Project(name=display, symbol="", source="Go Modules", raw_strength=3.0))
        return projects

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

    def _hacker_news_ask(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=story&query=Ask%20HN&hitsPerPage=100&page={page}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News Ask HN failed: %s", exc)
            return []

        projects: List[Project] = []
        for item in data.get("hits", []):
            title = item.get("title") or item.get("story_title") or ""
            if not title:
                continue
            # Strip "Ask HN:" prefix
            title = re.sub(r"^Ask\s+HN\s*[:\-]?\s*", "", title, flags=re.IGNORECASE).strip()
            name = re.split(r"\s*[-–|:]\s*", title, maxsplit=1)[0].strip()
            words = name.split()
            if len(words) > 5:
                name = " ".join(words[:5])
            if not name:
                continue
            points = item.get("points") or 0
            comments = item.get("num_comments") or 0
            strength = min(20.0, float(points) / 10 + float(comments) / 20)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News Ask HN",
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _hacker_news_new(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=100&page={page}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News new failed: %s", exc)
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
            strength = min(15.0, float(points) / 10 + float(comments) / 20)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News New",
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

    def _github_topic_repos(self, topic: str, days_offset: int) -> List[Project]:
        start = _days_ago(days_offset + 14)
        end = _days_ago(days_offset)
        query = quote(f"topic:{topic} stars:>10 created:{start}..{end}")
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("GitHub topic repos (topic=%s, offset=%s) failed: %s", topic, days_offset, exc)
            return []
        projects = []
        for item in data.get("items", []):
            name = item.get("name") or ""
            if not name:
                continue
            stars = item.get("stargazers_count") or 0
            strength = min(25.0, float(stars) / 50)
            projects.append(Project(
                name=name.replace("-", " ").replace("_", " "),
                symbol="",
                source=f"GitHub Topic ({topic})",
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

    def _wired_rss(self) -> List[Project]:
        url = "https://www.wired.com/feed/rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Wired RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Wired", base_strength=4.0)

    def _theverge_rss(self) -> List[Project]:
        url = "https://www.theverge.com/rss/index.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("The Verge RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "The Verge", base_strength=4.0)

    def _engadget_rss(self) -> List[Project]:
        url = "https://www.engadget.com/rss.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Engadget RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Engadget", base_strength=3.5)

    def _arstechnica_rss(self) -> List[Project]:
        url = "https://feeds.arstechnica.com/arstechnica/index"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Ars Technica RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Ars Technica", base_strength=3.5)

    def _fastcompany_rss(self) -> List[Project]:
        url = "https://www.fastcompany.com/latest/rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Fast Company RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Fast Company", base_strength=3.5)

    def _mashable_rss(self) -> List[Project]:
        url = "https://mashable.com/feeds/rss/all"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Mashable RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Mashable", base_strength=3.0)

    def _zdnet_rss(self) -> List[Project]:
        url = "https://www.zdnet.com/news/rss.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("ZDNet RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "ZDNet", base_strength=3.0)

    def _hackernoon_rss(self) -> List[Project]:
        url = "https://hackernoon.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker Noon RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Hacker Noon", base_strength=3.0)

    def _devto_rss(self) -> List[Project]:
        url = "https://dev.to/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Dev.to RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Dev.to", base_strength=3.0)

    def _indiehackers_rss(self) -> List[Project]:
        url = "https://www.indiehackers.com/feed.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Indie Hackers RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Indie Hackers", base_strength=4.0)

    def _saastr_rss(self) -> List[Project]:
        url = "https://www.saastr.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("SaaStr RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "SaaStr", base_strength=4.0)

    def _firstround_rss(self) -> List[Project]:
        url = "https://review.firstround.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("First Round Review RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "First Round Review", base_strength=4.0)

    def _a16z_rss(self) -> List[Project]:
        url = "https://a16z.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("A16Z RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "A16Z", base_strength=4.5)

    def _sequoia_rss(self) -> List[Project]:
        url = "https://www.sequoiacap.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Sequoia RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Sequoia", base_strength=4.5)

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

    def _npm_trending(self, offset: int) -> List[Project]:
        url = (
            f"https://registry.npmjs.org/-/v1/search"
            f"?text=is:unstable&popularity=1.0&quality=0.0&maintenance=0.0&size=100&from={offset}"
        )
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("npm trending (offset=%s) failed: %s", offset, exc)
            return []
        projects = []
        for obj in data.get("objects", []):
            name = obj.get("package", {}).get("name") or ""
            if not name:
                continue
            # Strip scope prefix (@scope/name -> name)
            display_name = name.split("/")[-1] if "/" in name else name
            display_name = display_name.replace("-", " ").replace("_", " ")
            if not display_name:
                continue
            score = obj.get("score", {}).get("final") or 0
            strength = min(15.0, float(score) * 15)
            projects.append(Project(
                name=display_name,
                symbol="",
                source="npm Trending",
                url=f"https://www.npmjs.com/package/{name}",
                raw_strength=strength,
            ))
        return projects

    def _pypi_top(self, pypi_offset: int) -> List[Project]:
        url = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages-30-days.min.json"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("PyPI top packages failed: %s", exc)
            return []
        projects = []
        rows = data.get("rows", [])
        page_rows = rows[pypi_offset: pypi_offset + 100]
        for i, row in enumerate(page_rows):
            name = row.get("project") or ""
            if not name:
                continue
            display_name = name.replace("-", " ").replace("_", " ")
            # Rank-based strength: earlier in list = higher rank = stronger signal
            rank = pypi_offset + i
            strength = max(1.0, 20.0 - rank * 0.1)
            projects.append(Project(
                name=display_name,
                symbol="",
                source="PyPI Top",
                url=f"https://pypi.org/project/{name}/",
                raw_strength=min(20.0, strength),
            ))
        return projects


    def _github_language_trending(self, language: str, days_offset: int) -> List[Project]:
        start = _days_ago(days_offset + 7)
        end = _days_ago(days_offset)
        query = quote(f"language:{language} stars:>50 created:>{start}..{end}")
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=100"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("GitHub language trending (lang=%s, offset=%s) failed: %s", language, days_offset, exc)
            return []
        projects = []
        for item in data.get("items", []):
            name = item.get("name") or ""
            if not name:
                continue
            stars = item.get("stargazers_count") or 0
            strength = min(25.0, float(stars) / 50)
            projects.append(Project(
                name=name.replace("-", " ").replace("_", " "),
                symbol="",
                source=f"GitHub Language ({language})",
                url=item.get("html_url"),
                raw_strength=strength,
            ))
        return projects

    def _hacker_news_jobs(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?tags=job&hitsPerPage=100&page={page}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News jobs failed: %s", exc)
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
            strength = min(15.0, float(points) / 10 + float(comments) / 20)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News Jobs",
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _hacker_news_who_is_hiring(self, page: int) -> List[Project]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query=who+is+hiring&tags=story&hitsPerPage=100&page={page}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("Hacker News who is hiring failed: %s", exc)
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
            strength = min(15.0, float(points) / 10 + float(comments) / 20)
            object_id = item.get("objectID")
            projects.append(
                Project(
                    name=name,
                    symbol="",
                    source="Hacker News Who Is Hiring",
                    url=f"https://news.ycombinator.com/item?id={object_id}" if object_id else item.get("url"),
                    raw_strength=strength,
                )
            )
        return projects

    def _lobsters_rss(self) -> List[Project]:
        url = "https://lobste.rs/rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Lobsters RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Lobsters", base_strength=3.5)

    def _slashdot_rss(self) -> List[Project]:
        url = "https://rss.slashdot.org/Slashdot/slashdotMain"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Slashdot RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Slashdot", base_strength=3.0)

    def _mit_tech_review_rss(self) -> List[Project]:
        url = "https://www.technologyreview.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("MIT Tech Review RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "MIT Tech Review", base_strength=4.0)

    def _ieee_spectrum_rss(self) -> List[Project]:
        url = "https://spectrum.ieee.org/rss/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("IEEE Spectrum RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "IEEE Spectrum", base_strength=3.5)

    def _smashing_magazine_rss(self) -> List[Project]:
        url = "https://www.smashingmagazine.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Smashing Magazine RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Smashing Magazine", base_strength=3.0)

    def _css_tricks_rss(self) -> List[Project]:
        url = "https://css-tricks.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("CSS Tricks RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "CSS Tricks", base_strength=3.0)

    def _webdesignernews_rss(self) -> List[Project]:
        url = "https://www.webdesignernews.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Web Designer News RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Web Designer News", base_strength=2.5)

    def _ux_collective_rss(self) -> List[Project]:
        url = "https://uxdesign.cc/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("UX Collective RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "UX Collective", base_strength=3.0)

    def _product_coalition_rss(self) -> List[Project]:
        url = "https://productcoalition.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Product Coalition RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Product Coalition", base_strength=3.0)

    def _yc_blog_rss(self) -> List[Project]:
        url = "https://www.ycombinator.com/blog/rss.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Y Combinator Blog RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Y Combinator Blog", base_strength=5.0)

    def _paulgraham_rss(self) -> List[Project]:
        url = "http://www.paulgraham.com/rss.html"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Paul Graham Essays RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Paul Graham Essays", base_strength=4.0)

    def _benedict_evans_rss(self) -> List[Project]:
        url = "https://www.ben-evans.com/benedictevans?format=rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Benedict Evans RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Benedict Evans", base_strength=4.0)

    def _stratechery_rss(self) -> List[Project]:
        url = "https://stratechery.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Stratechery RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Stratechery", base_strength=4.5)

    def _the_information_rss(self) -> List[Project]:
        url = "https://www.theinformation.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("The Information RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "The Information", base_strength=4.5)

    def _cbinsights_rss(self) -> List[Project]:
        url = "https://www.cbinsights.com/research/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("CB Insights RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "CB Insights", base_strength=4.0)

    def _steam_new_releases(self) -> List[Project]:
        url = "https://store.steampowered.com/feeds/newreleases.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Steam New Releases RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Steam New Releases", base_strength=3.0)

    def _rubygems_top(self, offset: int) -> List[Project]:
        url = f"https://rubygems.org/api/v1/search.json?query=&page={offset // 30 + 1}"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("RubyGems top failed: %s", exc)
            return []
        projects = []
        for gem in data:
            name = gem.get("name") or ""
            if not name:
                continue
            display = name.replace("-", " ").replace("_", " ")
            downloads = gem.get("downloads") or 0
            strength = min(20.0, float(downloads) / 1_000_000)
            projects.append(Project(name=display, symbol="", source="RubyGems", url=gem.get("project_uri"), raw_strength=max(1.0, strength)))
        return projects

    def _cratesio_top(self, offset: int) -> List[Project]:
        page = offset // 100 + 1
        url = f"https://crates.io/api/v1/crates?sort=downloads&per_page=100&page={page}"
        headers = {"User-Agent": self.session.headers.get("User-Agent", "bot")}
        try:
            resp = self.session.get(url, timeout=self.timeout, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            LOGGER.warning("Crates.io top failed: %s", exc)
            return []
        projects = []
        for crate in data.get("crates", []):
            name = crate.get("name") or ""
            if not name:
                continue
            display = name.replace("-", " ").replace("_", " ")
            downloads = crate.get("downloads") or 0
            strength = min(20.0, float(downloads) / 1_000_000)
            projects.append(Project(name=display, symbol="", source="Crates.io", raw_strength=max(1.0, strength)))
        return projects

    def _nuget_top(self, offset: int) -> List[Project]:
        url = f"https://azuresearch-usnc.nuget.org/query?q=&take=100&skip={offset}&sortBy=totalDownloads-desc"
        try:
            data = self._get_json(url)
        except requests.RequestException as exc:
            LOGGER.warning("NuGet top failed: %s", exc)
            return []
        projects = []
        for pkg in data.get("data", []):
            name = pkg.get("id") or ""
            if not name:
                continue
            display = name.replace(".", " ").replace("-", " ").replace("_", " ")
            strength = min(20.0, float(pkg.get("totalDownloads") or 0) / 10_000_000)
            projects.append(Project(name=display, symbol="", source="NuGet", raw_strength=max(1.0, strength)))
        return projects

    def _google_play_top(self) -> List[Project]:
        url = "https://rss.applemarketingtools.com/api/v2/us/apps/top-free/100/apps.json"
        # Reuse Apple structure for Google Play via RSS proxy
        url = "https://feeds.feedburner.com/GooglePlayNewApps"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Google Play RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Google Play", base_strength=4.0)

    def _thenextweb_rss(self) -> List[Project]:
        url = "https://thenextweb.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("The Next Web RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "The Next Web", base_strength=4.0)

    def _euStartups_rss(self) -> List[Project]:
        url = "https://eu-startups.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("EU Startups RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "EU Startups", base_strength=4.5)

    def _crunchbase_news_rss(self) -> List[Project]:
        url = "https://news.crunchbase.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Crunchbase News RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Crunchbase News", base_strength=5.0)

    def _infoq_rss(self) -> List[Project]:
        url = "https://feed.infoq.com/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("InfoQ RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "InfoQ", base_strength=3.5)

    def _dzone_rss(self) -> List[Project]:
        url = "https://feeds.dzone.com/home"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("DZone RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "DZone", base_strength=3.0)

    def _techrepublic_rss(self) -> List[Project]:
        url = "https://www.techrepublic.com/rssfeeds/articles/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("TechRepublic RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "TechRepublic", base_strength=3.0)

    def _sifted_rss(self) -> List[Project]:
        url = "https://sifted.eu/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Sifted RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Sifted", base_strength=4.5)

    def _betalist_rss(self) -> List[Project]:
        url = "https://betalist.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("BetaList RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "BetaList", base_strength=6.0)

    def _lobsters_rss(self) -> List[Project]:
        url = "https://lobste.rs/rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Lobsters RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Lobsters", base_strength=3.5)

    def _slashdot_rss(self) -> List[Project]:
        url = "https://rss.slashdot.org/Slashdot/slashdotMain"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Slashdot RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Slashdot", base_strength=3.0)

    def _mit_tech_review_rss(self) -> List[Project]:
        url = "https://www.technologyreview.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("MIT Tech Review RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "MIT Tech Review", base_strength=4.0)

    def _ieee_spectrum_rss(self) -> List[Project]:
        url = "https://spectrum.ieee.org/rss/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("IEEE Spectrum RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "IEEE Spectrum", base_strength=3.5)

    def _smashing_magazine_rss(self) -> List[Project]:
        url = "https://www.smashingmagazine.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Smashing Magazine RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Smashing Magazine", base_strength=3.0)

    def _css_tricks_rss(self) -> List[Project]:
        url = "https://css-tricks.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("CSS Tricks RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "CSS Tricks", base_strength=3.0)

    def _webdesignernews_rss(self) -> List[Project]:
        url = "https://www.webdesignernews.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Web Designer News RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Web Designer News", base_strength=2.5)

    def _ux_collective_rss(self) -> List[Project]:
        url = "https://uxdesign.cc/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("UX Collective RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "UX Collective", base_strength=3.0)

    def _product_coalition_rss(self) -> List[Project]:
        url = "https://productcoalition.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Product Coalition RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Product Coalition", base_strength=3.0)

    def _yc_blog_rss(self) -> List[Project]:
        url = "https://www.ycombinator.com/blog/rss.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Y Combinator Blog RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Y Combinator Blog", base_strength=5.0)

    def _paulgraham_rss(self) -> List[Project]:
        url = "http://www.paulgraham.com/rss.html"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Paul Graham Essays RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Paul Graham Essays", base_strength=4.0)

    def _benedict_evans_rss(self) -> List[Project]:
        url = "https://www.ben-evans.com/benedictevans?format=rss"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Benedict Evans RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Benedict Evans", base_strength=4.0)

    def _stratechery_rss(self) -> List[Project]:
        url = "https://stratechery.com/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Stratechery RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Stratechery", base_strength=4.5)

    def _the_information_rss(self) -> List[Project]:
        url = "https://www.theinformation.com/feed"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("The Information RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "The Information", base_strength=4.5)

    def _cbinsights_rss(self) -> List[Project]:
        url = "https://www.cbinsights.com/research/feed/"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("CB Insights RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "CB Insights", base_strength=4.0)

    def _steam_new_releases(self) -> List[Project]:
        url = "https://store.steampowered.com/feeds/newreleases.xml"
        try:
            text = self._get_text(url)
        except requests.RequestException as exc:
            LOGGER.warning("Steam New Releases RSS failed: %s", exc)
            return []
        return _parse_rss_titles(text, "Steam New Releases", base_strength=3.0)


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
