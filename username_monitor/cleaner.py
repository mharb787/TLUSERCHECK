import re
from typing import Iterable, List

BAD_WORDS = {
    "token",
    "coin",
    "official",
    "finance",
    "protocol",
    "network",
    "solana",
    "ethereum",
    "inc",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "company",
    "group",
    "holdings",
    "foundation",
    "labs",
    "lab",
    "studio",
    "studios",
    "beta",
    "alpha",
    "launch",
    "show",
    "hn",
}

MAX_USERNAME_LENGTH = 8
USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{3,31}$")


def clean_project_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"^show\s+hn\s*[:\-]\s*", " ", value)
    value = re.sub(r"\s*[-|:]\s*.*$", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    parts = [part for part in value.split() if part not in BAD_WORDS]
    return "".join(parts)


def is_quality_base(base: str) -> bool:
    if len(base) < 4 or len(base) > MAX_USERNAME_LENGTH:
        return False
    if base.isdigit():
        return False
    if len(set(base)) <= 2:
        return False
    if re.search(r"(.)\1{3,}", base):
        return False
    return True


def username_variations(project_name: str) -> List[str]:
    base = clean_project_name(project_name)
    if not is_quality_base(base):
        return []

    candidates = [
        base,
        f"get{base}",
        f"{base}app",
        f"{base}ai",
        f"{base}pay",
    ]
    seen = set()
    cleaned: List[str] = []
    for candidate in candidates:
        if len(candidate) > MAX_USERNAME_LENGTH:
            continue
        if candidate not in seen and USERNAME_RE.match(candidate):
            seen.add(candidate)
            cleaned.append(candidate)
    return cleaned


def unique_usernames(project_names: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for name in project_names:
        for username in username_variations(name):
            if username not in seen:
                seen.add(username)
                result.append(username)
    return result
