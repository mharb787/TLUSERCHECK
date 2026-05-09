import re
from typing import Iterable, List, Optional

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

MIN_USERNAME_LENGTH = 5
MAX_USERNAME_LENGTH = 10
USERNAME_RE = re.compile(r"^[a-z]{5,10}$")


def clean_project_name(value: str) -> str:
    word = extract_plain_word(value)
    return word or ""


def extract_plain_word(value: str) -> Optional[str]:
    value = value.lower()
    value = re.sub(r"^show\s+hn\s*[:\-]\s*", " ", value)
    value = re.sub(r"\s*[-|:]\s*.*$", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    parts = [part for part in value.split() if part not in BAD_WORDS]
    if len(parts) != 1:
        return None
    word = parts[0]
    if not USERNAME_RE.match(word):
        return None
    return word


def is_quality_base(base: str) -> bool:
    if len(base) < MIN_USERNAME_LENGTH or len(base) > MAX_USERNAME_LENGTH:
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
    return [base]


def unique_usernames(project_names: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for name in project_names:
        for username in username_variations(name):
            if username not in seen:
                seen.add(username)
                result.append(username)
    return result
