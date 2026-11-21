"""Операции верхнего уровня: дедупликация, обзор, желания, входные payload."""

import json
from datetime import datetime
from pathlib import Path

from . import strings as S
from .constants import CATEGORIES, CATEGORY_TITLES, DEDUP_CATEGORIES, THOUGHT_MAX_CHARS
from .resonance import (
    _find_duplicate,
    _flatten,
    _memory_key,
    _resonance_score,
    _short,
    _shorten_thought,
    _stem,
    _tokens,
)
from .storage import (
    _read_category,
    _write_category,
    delete_memory,
    load_memories,
    save_memory,
    save_text,
)


def dedup_all() -> str:
    lines = []
    for category in CATEGORIES:
        data = _read_category(category)
        memories = data.get("memories", [])
        if not memories:
            continue
        seen, keep, removed = {}, [], 0
        for memory in memories:
            key = _memory_key(memory)
            if not key or key == "|":
                keep.append(memory)
                continue
            if key in seen:
                removed += 1
                continue
            seen[key] = memory["id"]
            keep.append(memory)
        if removed:
            data["memories"] = keep
            _write_category(category, data)
            lines.append(
                S.MSG_DEDUP_REMOVED.format(category=category, removed=removed)
            )
    return (
        S.MSG_DEDUP_HEADER + "\n" + "\n".join(lines) if lines else S.MSG_DEDUP_NONE
    )


def read_all_memories() -> str:
    lines = []
    desires = load_memories("desires")
    if desires:
        lines.append(S.HEADER_DESIRES)
        for m in desires:
            lines.append(
                S.LINE_DESIRE.format(id=m["id"], text=_flatten(m.get("content", {})))
            )
        lines.append("")
    for cat in CATEGORIES:
        if cat == "desires":
            continue
        memories = load_memories(cat)
        if not memories:
            continue
        lines.append(
            S.HEADER_CATEGORY.format(
                cat=cat, title=CATEGORY_TITLES[cat], count=len(memories)
            )
        )
        for m in memories:
            lines.append(
                S.LINE_MEMORY.format(
                    id=m["id"],
                    date=str(m.get("created_at", ""))[:10],
                    text=_short(_flatten(m.get("content", {}))),
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() if lines else S.MSG_MEMORY_EMPTY


def get_memory_count(category: str) -> int:
    return len(load_memories(category))


def finish_desire(needle: str) -> str:
    desires = load_memories("desires")
    if not desires:
        return S.MSG_NO_DESIRES
    target = next((m for m in desires if m.get("id") == needle), None)
    if not target:
        scored = [
            (_resonance_score([_stem(t) for t in _tokens(needle)], m), m)
            for m in desires
        ]
        scored.sort(key=lambda p: p[0], reverse=True)
        target = scored[0][1] if scored else None
    if not target:
        return S.MSG_DESIRE_NOT_FOUND.format(needle=needle)
    text = _flatten(target.get("content", {}))
    delete_memory("desires", target["id"])
    entry = save_text(
        "deeds",
        S.DESIRE_DEED_TEXT.format(
            date=datetime.now().strftime("%d.%m.%Y"), text=text
        ),
        [S.TAG_DEED],
    )
    return S.MSG_DESIRE_CLOSED.format(
        id=target["id"], text=text, trace_id=entry["id"]
    )


def remember_payload(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    facts = (
        payload
        if isinstance(payload, list)
        else (
            payload.get("facts", [payload]) if isinstance(payload, dict) else [payload]
        )
    )
    if not facts:
        return S.MSG_EMPTY_FACTS
    lines = []
    for fact in facts:
        content = fact.get("content") or {"text": fact.get("text", "")}
        if not content:
            lines.append(S.MSG_FACT_SKIPPED)
            continue
        category = fact.get("category", "thoughts")
        tags = list(fact.get("tags", []))
        if category in DEDUP_CATEGORIES:
            existing = _find_duplicate(category, _flatten(content), tags)
            if existing:
                lines.append(
                    S.MSG_FACT_DUPLICATE.format(
                        id=existing["id"], category=category
                    )
                )
                continue
        entry = save_memory(category, content, tags)
        lines.append(
            S.MSG_FACT_SAVED.format(id=entry["id"], category=entry["category"])
        )
    return S.MSG_REMEMBER_HEADER + "\n" + "\n".join(lines)


def think_payload(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text, desire = (
        (payload.get("text") or "").strip(),
        (payload.get("desire") or "").strip(),
    )
    if not text and not desire:
        return S.MSG_THINK_EMPTY
    lines = []
    if text:
        thought = _find_duplicate("thoughts", text, list(payload.get("tags", [])))
        if not thought:
            saved_text, cut = _shorten_thought(text)
            thought = save_text("thoughts", saved_text, list(payload.get("tags", [])))
            lines.append(S.MSG_THOUGHT.format(id=thought["id"]))
            if cut:
                lines.append(S.MSG_THOUGHT_SHORTENED.format(limit=THOUGHT_MAX_CHARS))
        else:
            lines.append(S.MSG_THOUGHT_DUPLICATE.format(id=thought["id"]))
    if desire:
        existing = _find_duplicate("desires", desire, [S.TAG_DESIRE])
        if not existing:
            entry = save_text("desires", desire, [S.TAG_DESIRE])
            lines.append(S.MSG_DESIRE_SAVED.format(id=entry["id"], desire=desire))
        else:
            lines.append(
                S.MSG_DESIRE_EXISTS.format(id=existing["id"], desire=desire)
            )
    return "\n".join(lines)
