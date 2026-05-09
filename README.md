# Telegram Username Opportunity Monitor

Python bot that monitors public crypto project sources, generates Telegram username ideas, checks public Fragment pages, scores opportunities, and sends Telegram alerts.

This project is monitoring-only. It does not connect wallets, log in to Telegram, buy usernames, bid on auctions, or use account sessions.

## What It Does

- Runs every 5 minutes with GitHub Actions.
- Collects candidates only from crypto coin/token sources such as DexScreener, CoinGecko, and CoinPaprika.
- Cleans project names and checks only the plain original word.
- Does not generate prefixes or suffixes such as `get`, `ai`, `app`, or `pay`.
- Checks public Fragment username pages only.
- Treats missing Fragment pages as `No Fragment listing`, not as confirmed Telegram availability.
- Sends alerts only when Fragment shows the `unavailable` label, based on the observed claimable-name wording.
- Scores each username from 1 to 100.
- Only checks plain English-letter words from 6 to 7 characters.
- Sends up to 10 new Telegram alerts per run by default.
- Checks up to 500 new usernames per run by default.
- Stores checked usernames in `data/checked_usernames.json` to avoid repeating alerts in future runs.

## Setup

1. Create a Telegram bot with BotFather and copy the bot token.
2. Send `/start` to your bot.
3. In GitHub, open `Settings -> Secrets and variables -> Actions`.
4. Add this repository secret:

| Secret | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |

The workflow currently sends alerts to chat ID `12204622`.

## GitHub Actions Schedule

The workflow is in `.github/workflows/telegram-monitor.yml`.

GitHub Actions scheduled workflows support a minimum interval of 5 minutes, so the bot runs with:

```yaml
cron: "*/5 * * * *"
```

Each run sends up to 10 suggestions, or fewer if fewer `unavailable` opportunities are found.

## Environment Variables

| Variable | Default | Description |
| --- | ---: | --- |
| `TELEGRAM_BOT_TOKEN` | empty | Telegram bot token |
| `TELEGRAM_CHAT_ID` | `12204622` | Telegram chat ID used by the workflow |
| `MAX_ALERTS_PER_RUN` | `10` | Maximum alerts per workflow run |
| `MAX_USERNAMES_TO_CHECK` | `500` | Maximum new usernames to check per workflow run |
| `MIN_SCORE` | `81` | Minimum score required for alerts |
| `REQUEST_TIMEOUT` | `20` | HTTP timeout in seconds |
| `CACHE_PATH` | `data/checked_usernames.json` | Local username cache path |
| `DRY_RUN` | `false` | Log alerts without sending Telegram messages |

## Local Run

```bash
pip install -r requirements.txt
DRY_RUN=true python main.py
```

On Windows PowerShell:

```powershell
$env:DRY_RUN="true"
python main.py
```

## Alert Example

```text
New Username Opportunity

Project: orbit
Source: DexScreener
Liquidity: $240K
24h Volume: N/A
Telegram Username: @orbit
Fragment Status: Unavailable
Score: 86/100
Why: compact, pronounceable, clean spelling, exact project match
```

## Notes

- Fragment checks are based on public web pages and can change if Fragment changes its HTML.
- A missing Fragment page does not prove that a username can be claimed inside Telegram.
- Fragment wording can be counterintuitive: this monitor only alerts on `unavailable` and ignores auction/taken/unknown statuses.
- A score is a heuristic, not a guarantee of market value.
- The cache file is committed back to the repository after each run so the next scheduled run does not repeat the same usernames.
