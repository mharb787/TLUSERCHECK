import logging
from collections import Counter
from typing import List

from .cleaner import username_variations
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
    LOGGER.info("Collected %s projects", len(projects))

    opportunities: List[UsernameOpportunity] = []
    checked_this_run = set()
    status_counts: Counter[str] = Counter()

    for project in projects:
        for username in username_variations(project.name):
            key = username.lower()
            if key in checked_this_run or store.seen(username):
                continue
            if len(checked_this_run) >= config.max_usernames_to_check:
                LOGGER.info("Reached MAX_USERNAMES_TO_CHECK=%s", config.max_usernames_to_check)
                break
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
        if len(opportunities) >= config.max_alerts_per_run or len(checked_this_run) >= config.max_usernames_to_check:
            break

    opportunities.sort(key=lambda item: item.score, reverse=True)
    notifier.send_opportunities(opportunities[: config.max_alerts_per_run])
    store.save()
    LOGGER.info("Fragment status counts: %s", dict(status_counts))
    LOGGER.info("Sent %s alerts; checked %s new usernames", len(opportunities), len(checked_this_run))
