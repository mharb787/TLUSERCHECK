import logging
from collections import Counter
from typing import List

from .cleaner import username_variations, is_quality_base, clean_project_name
from .config import load_config
from .fragment import FragmentClient
from .models import UsernameOpportunity
from .scoring import score_username
from .sources import SourceClient
from .storage import CheckedStore
from .telegram import TelegramNotifier

LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    config = load_config()
    store = CheckedStore(config.cache_path)
    store.load()

    sources = SourceClient(timeout=config.request_timeout, user_agent=config.user_agent)
    fragment = FragmentClient(timeout=config.request_timeout, user_agent=config.user_agent, bot_token=config.telegram_bot_token)
    notifier = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        timeout=config.request_timeout,
        dry_run=config.dry_run,
    )

    projects = sources.collect_projects()
    total_projects = len(projects)
    LOGGER.info("Collected %s projects", total_projects)

    filtered_strength = 0
    filtered_cleaner = 0
    filtered_cache = 0
    filtered_score = 0
    opportunities: List[UsernameOpportunity] = []
    checked_this_run = set()
    status_counts: Counter[str] = Counter()

    for project in projects:
        if project.raw_strength < config.min_project_strength:
            filtered_strength += 1
            continue
        candidate = clean_project_name(project.name)
        if not candidate or not is_quality_base(candidate):
            filtered_cleaner += 1
            continue
        key = candidate.lower()
        if key in checked_this_run or store.seen(candidate):
            filtered_cache += 1
            continue
        if len(checked_this_run) >= config.max_usernames_to_check:
            LOGGER.info("Reached MAX_USERNAMES_TO_CHECK=%s", config.max_usernames_to_check)
            break
        checked_this_run.add(key)

        score, reason = score_username(candidate, project)
        fragment_result = fragment.check_username(candidate)
        status_counts[fragment_result.status] += 1
        should_alert = fragment_result.status == "Unavailable"

        store.mark(
            candidate,
            {
                "project": project.name,
                "source": project.source,
                "score": score,
                "fragment_status": fragment_result.status,
            },
        )

        if should_alert and score < config.min_score:
            filtered_score += 1

        if should_alert and score >= config.min_score:
            opportunities.append(
                UsernameOpportunity(
                    project=project,
                    username=candidate,
                    fragment_status=fragment_result.status,
                    score=score,
                    reason=reason,
                )
            )
            LOGGER.info("Opportunity @%s score=%s status=%s", candidate, score, fragment_result.status)

        if len(opportunities) >= config.max_alerts_per_run:
            break

    opportunities.sort(key=lambda item: item.score, reverse=True)
    notifier.send_opportunities(opportunities[: config.max_alerts_per_run])
    store.save()

    LOGGER.info("Fragment status counts: %s", dict(status_counts))
    LOGGER.info("Sent %s alerts; checked %s new usernames", len(opportunities), len(checked_this_run))

    notifier.send_message(_build_report(
        total_projects=total_projects,
        filtered_strength=filtered_strength,
        filtered_cleaner=filtered_cleaner,
        filtered_cache=filtered_cache,
        checked=len(checked_this_run),
        status_counts=status_counts,
        filtered_score=filtered_score,
        alerts_sent=len(opportunities),
    ))


def _build_report(
    total_projects: int,
    filtered_strength: int,
    filtered_cleaner: int,
    filtered_cache: int,
    checked: int,
    status_counts: Counter,
    filtered_score: int,
    alerts_sent: int,
) -> str:
    unavailable = status_counts.get("Unavailable", 0) + status_counts.get("Taken in Telegram", 0)
    lines = [
        "📊 <b>تقرير الدورة</b>",
        "",
        f"📥 مشاريع جُمعت: <b>{total_projects}</b>",
        f"🔻 حُذف (قوة منخفضة): <b>{filtered_strength}</b>",
        f"🔻 حُذف (فلتر الحروف): <b>{filtered_cleaner}</b>",
        f"🔻 موجود في الكاش: <b>{filtered_cache}</b>",
        "",
        f"🔍 تم فحصه على Fragment: <b>{checked}</b>",
        f"   • Unavailable: <b>{status_counts.get('Unavailable', 0)}</b>",
        f"   • Auction: <b>{status_counts.get('Auction', 0)}</b>",
        f"   • Taken: <b>{status_counts.get('Taken', 0) + status_counts.get('Taken in Telegram', 0)}</b>",
        f"   • Other: <b>{status_counts.get('Unknown', 0) + status_counts.get('No Fragment listing', 0)}</b>",
        "",
        f"🔻 حُذف (درجة منخفضة): <b>{filtered_score}</b>",
        f"🚨 تنبيهات أُرسلت: <b>{alerts_sent}</b>",
    ]
    return "\n".join(lines)
