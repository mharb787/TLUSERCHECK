# Telegram Username Opportunity Monitor

Python bot that monitors public crypto project sources, generates Telegram username ideas, checks public Fragment pages, scores opportunities, and sends Telegram alerts.

This project is monitoring-only. It does not connect wallets, log in to Telegram, buy usernames, bid on auctions, or use account sessions.

## What It Does

- Runs every 5 minutes with GitHub Actions.
- Collects projects from:
  - DexScreener latest token profiles
  - DexScreener latest/top boosts
  - CoinGecko trending coins
- Cleans project names and generates username variations:
  - `projectname`
  - `getprojectname`
  - `projectnameapp`
  - `projectnameai`
  - `projectpay`
- Checks public Fragment username pages only.
- Treats missing Fragment pages as `No Fragment listing`, not as confirmed Telegram availability.
- Treats Fragment `unavailable` labels as username opportunities, based on the observed Fragment wording.
- Scores each username from 1 to 100.
- Sends up to 10 new Telegram alerts per run by default.
- Checks up to 80 new usernames per run by default.
- Stores checked usernames in `data/checked_usernames.json` to avoid repeating alerts in future runs.

## Setup

1. Create a Telegram bot with BotFather and copy the bot token.
2. Get your Telegram chat ID.
3. Push this project to a GitHub repository.
4. In GitHub, open `Settings -> Secrets and variables -> Actions`.
5. Add these repository secrets:

| Secret | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID that should receive alerts |

## GitHub Actions Schedule

The workflow is in `.github/workflows/telegram-monitor.yml`.

GitHub Actions scheduled workflows support a minimum interval of 5 minutes, so the bot runs with:

```yaml
cron: "*/5 * * * *"
```

Each run sends up to 10 suggestions, or fewer if fewer strong new opportunities are found.

## Environment Variables

| Variable | Default | Description |
| --- | ---: | --- |
| `TELEGRAM_BOT_TOKEN` | empty | Telegram bot token |
| `TELEGRAM_CHAT_ID` | empty | Telegram chat ID |
| `MAX_ALERTS_PER_RUN` | `10` | Maximum alerts per workflow run |
| `MAX_USERNAMES_TO_CHECK` | `80` | Maximum new usernames to check per workflow run |
| `MIN_SCORE` | `70` | Minimum score required for alerts |
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
🚨 New Username Opportunity

Project: CASHOME
Source: DexScreener
Liquidity: $240K
24h Volume: N/A
Telegram Username: @cashome
Fragment Status: Available
Score: 86/100
Why: compact, pronounceable, clean spelling, exact project match
```

## Notes

- Fragment checks are based on public web pages and can change if Fragment changes its HTML.
- A missing Fragment page does not prove that a username can be claimed inside Telegram.
- Fragment wording can be counterintuitive: this monitor treats `unavailable` as the claimable/opportunity signal.
- A score is a heuristic, not a guarantee of market value.
- The cache file is committed back to the repository after each run so the next scheduled run does not repeat the same usernames.
