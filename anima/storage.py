"""Хранилище категорий: шаблоны, чтение, запись, генерация ID."""

import json
from datetime import datetime, timezone

from .constants import CATEGORIES, MEMORY_DIR
from .strings import MSG_UNKNOWN_CATEGORY


def _template(category: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"{category}_template",
        "category": category,
        "content": {},
        "created_at": ts,
        "updated_at": ts,
        "tags": [],
        "memories": [],
    }


def init_memory_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    for cat in CATEGORIES:
        path = MEMORY_DIR / f"{cat}.json"
        if not path.exists():
            path.write_text(
                json.dumps(_template(cat), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def _read_category(category: str) -> dict:
    path = MEMORY_DIR / f"{category}.json"
    return (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else _template(category)
    )


def _write_category(category: str, data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    (MEMORY_DIR / f"{category}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _next_id(category: str, memories: list) -> str:
    max_n = 0
    for m in memories:
        mid = str(m.get("id", ""))
        if mid.startswith(f"{category}_"):
            try:
                max_n = max(max_n, int(mid.rsplit("_", 1)[-1]))
            except ValueError:
                continue
    return f"{category}_{max_n + 1:03d}"


def save_memory(category: str, content: dict, tags: list | None = None) -> dict:
    if category not in CATEGORIES:
        raise ValueError(MSG_UNKNOWN_CATEGORY.format(category=category))
    data = _read_category(category)
    memories = data.setdefault("memories", [])
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": _next_id(category, memories),
        "category": category,
        "content": content,
        "created_at": ts,
        "updated_at": ts,
        "tags": list(tags or []),
    }
    memories.append(entry)
    _write_category(category, data)
    return entry


def save_text(category: str, text: str, tags: list | None = None) -> dict:
    return save_memory(category, {"text": text.strip()}, tags)


def load_memories(category: str) -> list:
    return _read_category(category).get("memories", [])


def delete_memory(category: str, memory_id: str) -> bool:
    data = _read_category(category)
    memories = data.get("memories", [])
    remaining = [m for m in memories if m.get("id") != memory_id]
    if len(remaining) == len(memories):
        return False
    data["memories"] = remaining
    _write_category(category, data)
    return True
