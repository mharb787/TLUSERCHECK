import re
from typing import Tuple

from .cleaner import clean_project_name
from .models import Project

CRYPTO_AI_TERMS = ("ai", "pay", "swap", "dex", "chain", "lab", "labs", "cash", "base", "data", "agent")
VOWELS = set("aeiou")


def score_username(username: str, project: Project) -> Tuple[int, str]:
    score = 35
    reasons = []

    length = len(username)
    if length <= 6:
        score += 20
        reasons.append("short")
    elif length <= 10:
        score += 14
        reasons.append("compact")
    elif length <= 14:
        score += 8

    if any(term in username for term in CRYPTO_AI_TERMS):
        score += 10
        reasons.append("crypto/AI relevant")

    if _pronounceable(username):
        score += 12
        reasons.append("pronounceable")

    if re.fullmatch(r"[a-z][a-z0-9]{3,31}", username) and "__" not in username:
        score += 10
        reasons.append("clean spelling")

    if username == clean_project_name(project.name) or username == _normalized(project.name):
        score += 10
        reasons.append("exact project match")
    strength_bonus = min(18, int(project.raw_strength))
    if strength_bonus:
        score += strength_bonus
        reasons.append("source strength")

    return max(1, min(100, score)), ", ".join(reasons) or "baseline"


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _pronounceable(value: str) -> bool:
    if not any(char in VOWELS for char in value):
        return False
    consonant_runs = re.findall(r"[^aeiou0-9]{4,}", value)
    return not consonant_runs
