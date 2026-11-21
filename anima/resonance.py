"""Резонансный поиск: синонимы, нормализация текста и скоринг."""

import json
import re
from datetime import datetime, timezone

from .constants import (
    _FRESH_DAYS,
    _RU_SUFFIXES,
    CATEGORIES,
    DEDUP_CATEGORIES,
    NEAR_DUPLICATE_RATIO,
    NEAR_DUPLICATE_WINDOW,
    SYNONYM_FILE,
    THOUGHT_MAX_CHARS,
    THOUGHTS_WEIGHT_DEN,
    THOUGHTS_WEIGHT_NUM,
)
from .storage import load_memories


def load_synonyms() -> dict:
    if not SYNONYM_FILE.exists():
        return {"groups": [], "categories": {}}
    try:
        data = json.loads(SYNONYM_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"groups": [], "categories": {}}
    data.setdefault("groups", [])
    data.setdefault("categories", {})
    return data


def _stem(word: str) -> str:
    word = word.lower().replace("ё", "е")
    if len(word) <= 4:
        return word
    for suf in _RU_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word[:5] if len(word) > 5 else word


SYNONYM_DATA = load_synonyms()
SYNONYM_NET = {}
for _group in SYNONYM_DATA["groups"]:
    _stems = {_stem(w) for w in _group}
    for _s in _stems:
        SYNONYM_NET.setdefault(_s, set()).update(_stems)

CATEGORY_HINTS = {}
for _cat, _words in SYNONYM_DATA["categories"].items():
    for _w in _words:
        CATEGORY_HINTS.setdefault(_stem(_w), set()).add(_cat)


def _tokens(text: str) -> list:
    return re.findall(r"[а-яёa-z0-9]+", text.lower())


def _normalize(text: str) -> str:
    text = text.lower().strip().replace("ё", "е")
    text = re.sub(r"[—–−]", "-", text)
    return re.sub(r"\s+", " ", text).strip(" .,:;!?\"'«»")


def _flatten(content: dict) -> str:
    if not content:
        return ""
    if set(content.keys()) == {"text"}:
        return str(content["text"])
    return "; ".join(f"{k}: {v}" for k, v in content.items())


def _memory_key(memory: dict) -> str:
    text = _normalize(_flatten(memory.get("content", {})))
    tags = ",".join(sorted(_normalize(str(t)) for t in memory.get("tags", [])))
    return f"{text}|{tags}"


def _stems(text: str) -> set:
    return {_stem(t) for t in _tokens(text) if len(t) >= 4}


def _jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _find_paraphrase(category: str, text: str) -> dict | None:
    if category not in DEDUP_CATEGORIES:
        return None
    needle = _stems(text)
    if len(needle) < 4:
        return None
    for memory in reversed(load_memories(category)[-NEAR_DUPLICATE_WINDOW:]):
        stored = _stems(_flatten(memory.get("content", {})))
        if len(stored) < 4:
            continue
        ratio = len(needle) / max(1, len(stored))
        if 0.6 <= ratio <= 1.7 and _jaccard(needle, stored) >= NEAR_DUPLICATE_RATIO:
            return memory
    return None


def _shorten_thought(text: str) -> tuple[str, bool]:
    if len(text) <= THOUGHT_MAX_CHARS:
        return text, False
    window = text[:THOUGHT_MAX_CHARS]
    cut = max(
        window.rfind("."), window.rfind("!"), window.rfind("?"), window.rfind("…")
    )
    if cut < THOUGHT_MAX_CHARS // 3:
        cut = window.rfind(" ")
    if cut <= 0:
        cut = THOUGHT_MAX_CHARS
    return window[:cut].rstrip(" ,;:—-"), True


def _find_duplicate(category: str, text: str, tags: list | None = None) -> dict | None:
    key = f"{_normalize(text)}|{','.join(sorted(_normalize(str(t)) for t in (tags or [])))}"
    if key.startswith("|"):
        return None
    for memory in load_memories(category):
        if _memory_key(memory) == key:
            return memory
    return _find_paraphrase(category, text)


def _memory_text(memory: dict) -> str:
    parts = [json.dumps(memory.get("content", {}), ensure_ascii=False)]
    parts.extend(str(t) for t in memory.get("tags", []))
    return " ".join(parts)


def _freshness_bonus(memory: dict) -> float:
    cat = memory.get("category")
    if cat not in _FRESH_DAYS:
        return 0.0
    try:
        age_days = (
            datetime.now(timezone.utc) - datetime.fromisoformat(memory["created_at"])
        ).days
    except (KeyError, ValueError):
        return 0.0
    window = _FRESH_DAYS[cat]
    return 1.0 - age_days / window if age_days <= window else 0.0


def _resonance_score(query_stems: list, memory: dict) -> float:
    text_stems = {_stem(t) for t in _tokens(_memory_text(memory))}
    tag_stems = {_stem(t) for t in memory.get("tags", [])}
    memory_category = memory.get("category")

    hits = sum(1 for q in query_stems if q in text_stems)
    synonym_hits = sum(1 for q in query_stems if SYNONYM_NET.get(q, set()) & text_stems)

    score = hits * 5 + synonym_hits * 3
    if hits + synonym_hits >= 2:
        score += (hits + synonym_hits - 1) * 2

    for q in query_stems:
        if q in tag_stems:
            score += 3
        if memory_category in CATEGORY_HINTS.get(q, set()):
            score += 2
        if q == _stem(memory_category):
            score += 2

    score += sum(1 for q in query_stems if len(q) >= 5)
    if memory_category == "thoughts":
        score = score * THOUGHTS_WEIGHT_NUM / THOUGHTS_WEIGHT_DEN
    score += _freshness_bonus(memory) * 2
    return score


def search_memories(query: str, category: str | None = None, limit: int = 10) -> list:
    query_stems = [_stem(t) for t in _tokens(query)]
    if not query_stems:
        return []
    scored = []
    for cat in [category] if category else CATEGORIES:
        if cat not in CATEGORIES:
            continue
        for memory in load_memories(cat):
            score = _resonance_score(query_stems, memory)
            if score > 0:
                scored.append((score, memory))
    scored.sort(key=lambda p: p[0], reverse=True)
    return [{**m, "_score": s} for s, m in scored[:limit]]


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"
