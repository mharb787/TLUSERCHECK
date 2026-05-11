import logging
from collections import Counter
from typing import List

from .cleaner import username_variations
from .config import load_config
from .fragment import FragmentClient
from .models import Project, UsernameOpportunity
from .pagination import PaginationState
from .queue_store import QueueStore
from .scoring import score_username
from .sources import SourceClient
from .storage import CheckedStore
from .telegram import TelegramNotifier

LOGGER = logging.getLogger(__name__)

_BATCH_SIZE = 20


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    config = load_config()

    # Step 1: Load stores
    queue = QueueStore()
    queue.load()

    pagination_state = PaginationState()
    pagination_state.load()

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

    fetched_new_sources = False
    total_projects = 0

    # Step 4: If queue is empty, fetch new projects from sources
    if queue.is_empty():
        LOGGER.info("Queue is empty; fetching new projects from sources")
        projects = sources.collect_projects(pagination_state)
        total_projects = len(projects)
        LOGGER.info("Collected %s projects from sources", total_projects)
        fetched_new_sources = True

        # Convert projects to queue items
        queue_items = [
            {"name": project.name, "source": project.source, "raw_strength": project.raw_strength}
            for project in projects
            if project.raw_strength >= config.min_project_strength
        ]
        queue.push_back(queue_items)
        LOGGER.info("Added %s items to queue", len(queue_items))
    else:
        LOGGER.info("Queue has %s items; processing without fetching new sources", queue.size())

    # Step 5: Process queue items
    opportunities: List[UsernameOpportunity] = []
    checked_this_run: set = set()
    status_counts: Counter = Counter()
    leftover_items: list = []

    while not queue.is_empty() and len(opportunities) < config.max_alerts_per_run and len(checked_this_run) < config.max_usernames_to_check:
        batch = queue.pop_batch(_BATCH_SIZE)

        for item in batch:
            if len(opportunities) >= config.max_alerts_per_run or len(checked_this_run) >= config.max_usernames_to_check:
                idx = batch.index(item)
                leftover_items = batch[idx:] + leftover_items
                break

            project = Project(
                name=item["name"],
                symbol="",
                source=item["source"],
                raw_strength=item.get("raw_strength", 0.0),
            )

            for username in username_variations(project.name):
                key = username.lower()
                if key in checked_this_run or store.seen(username):
                    continue

                checked_this_run.add(key)
                score, reason = score_username(username, project)
                fragment_result = fragment.check_username(username)
                status_counts[fragment_result.status] += 1
                should_alert = fragment_result.status == "Unavailable"

                store.mark(
                    username,
                    {
                        "project": project.name,
                        "source": project.source,
                        "score": score,
                        "fragment_status": fragment_result.status,
                    },
                )

                if should_alert and score >= config.min_score:
                    opportunities.append(
                        UsernameOpportunity(
                            project=project,
                            username=username,
                            fragment_status=fragment_result.status,
                            score=score,
                            reason=reason,
                        )
                    )
                    LOGGER.info("Opportunity @%s score=%s status=%s", username, score, fragment_result.status)

                if len(opportunities) >= config.max_alerts_per_run:
                    break

    # Step 6: Save remaining queue items back
    if leftover_items:
        queue.push_back(leftover_items)
    queue.save()

    # Step 7: Save pagination state (only advance if we actually fetched new sources)
    if fetched_new_sources:
        pagination_state.save()

    # Step 8: Send opportunities + summary
    opportunities.sort(key=lambda item: item.score, reverse=True)
    notifier.send_opportunities(opportunities[: config.max_alerts_per_run])
    store.save()

    LOGGER.info("Fragment status counts: %s", dict(status_counts))
    LOGGER.info(
        "Sent %s alerts; checked %s new usernames; queue remaining: %s",
        len(opportunities),
        len(checked_this_run),
        queue.size(),
    )

    notifier.send_message(_build_report(
        total_projects=total_projects,
        queue_remaining=queue.size(),
        checked=len(checked_this_run),
        status_counts=status_counts,
        alerts_sent=len(opportunities),
    ))


def _build_report(
    total_projects: int,
    queue_remaining: int,
    checked: int,
    status_counts: Counter,
    alerts_sent: int,
) -> str:
    lines = [
        "📊 <b>تقرير الدورة</b>",
        "",
        f"📥 مشاريع جُمعت: <b>{total_projects}</b>",
        f"📋 في الانتظار (queue): <b>{queue_remaining}</b>",
        "",
        f"🔍 تم فحصه على Fragment: <b>{checked}</b>",
        f"   • Unavailable: <b>{status_counts.get('Unavailable', 0)}</b>",
        f"   • Auction: <b>{status_counts.get('Auction', 0)}</b>",
        f"   • Taken: <b>{status_counts.get('Taken', 0) + status_counts.get('Taken in Telegram', 0)}</b>",
        f"   • Other: <b>{status_counts.get('Unknown', 0) + status_counts.get('No Fragment listing', 0)}</b>",
        "",
        f"🚨 تنبيهات أُرسلت: <b>{alerts_sent}</b>",
    ]
    return "\n".join(lines)
