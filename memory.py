import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).parent
MEMORY_DIR = ROOT / "memory"
SYNONYM_FILE = ROOT / "synonyms.json"
CATEGORIES = [
    "identity",
    "preferences",
    "relationships",
    "skills",
    "knowledge",
    "thoughts",
    "desires",
    "deeds",
]
CATEGORY_TITLES = {
    "identity": "кто я",
    "preferences": "вкусы",
    "relationships": "люди",
    "skills": "умения",
    "knowledge": "знания",
    "thoughts": "мысли",
    "desires": "чего хочу",
    "deeds": "что сделано",
}
DEDUP_CATEGORIES = ("desires", "thoughts")
THOUGHTS_WEIGHT_NUM, THOUGHTS_WEIGHT_DEN = 3, 4
THOUGHT_MAX_CHARS = 400
NEAR_DUPLICATE_RATIO, NEAR_DUPLICATE_WINDOW = 0.5, 40
_FRESH_DAYS = {"thoughts": 14, "desires": 30}

_RU_SUFFIXES = (
    "ость",
    "ения",
    "ания",
    "ами",
    "ями",
    "ого",
    "его",
    "ему",
    "ому",
    "ая",
    "яя",
    "ый",
    "ий",
    "ой",
    "ей",
    "ую",
    "юю",
    "ые",
    "ие",
    "ых",
    "их",
    "ым",
    "им",
    "ом",
    "ем",
    "ать",
    "ять",
    "еть",
    "ить",
    "ешь",
    "ишь",
    "ут",
    "ют",
    "ат",
    "ят",
    "ла",
    "ло",
    "ли",
    "на",
    "но",
    "ны",
    "ён",
    "ен",
    "ся",
    "сь",
)


def _stem(word: str) -> str:
    word = word.lower().replace("ё", "е")
    if len(word) <= 4:
        return word
    for suf in _RU_SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word[:5] if len(word) > 5 else word


def _tokens(text: str) -> list:
    return re.findall(r"[а-яёa-z0-9]+", text.lower())


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


def save_memory(category: str, content: dict, tags: Optional[list] = None) -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"Неизвестная категория: {category}")
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


def save_text(category: str, text: str, tags: Optional[list] = None) -> dict:
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


def _find_paraphrase(category: str, text: str) -> Optional[dict]:
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


def _find_duplicate(
    category: str, text: str, tags: Optional[list] = None
) -> Optional[dict]:
    key = f"{_normalize(text)}|{','.join(sorted(_normalize(str(t)) for t in (tags or [])))}"
    if key.startswith("|"):
        return None
    for memory in load_memories(category):
        if _memory_key(memory) == key:
            return memory
    return _find_paraphrase(category, text)


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
            lines.append(f"  {category}: удалено дублей — {removed}")
    return "Почищено:\n" + "\n".join(lines) if lines else "Дублей не нашлось."


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


def search_memories(
    query: str, category: Optional[str] = None, limit: int = 10
) -> list:
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


def read_all_memories() -> str:
    lines = []
    desires = load_memories("desires")
    if desires:
        lines.append("ЧЕГО ХОЧУ (ещё не сделано):")
        for m in desires:
            lines.append(f"  {m['id']}  {_flatten(m.get('content', {}))}")
        lines.append("")
    for cat in CATEGORIES:
        if cat == "desires":
            continue
        memories = load_memories(cat)
        if not memories:
            continue
        lines.append(f"--- {cat} · {CATEGORY_TITLES[cat]} ({len(memories)}) ---")
        for m in memories:
            lines.append(
                f"  {m['id']} [{str(m.get('created_at', ''))[:10]}] {_short(_flatten(m.get('content', {})))}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() if lines else "Память пуста. Это начало."


def get_memory_count(category: str) -> int:
    return len(load_memories(category))


def finish_desire(needle: str) -> str:
    desires = load_memories("desires")
    if not desires:
        return "Незакрытых желаний нет."
    target = next((m for m in desires if m.get("id") == needle), None)
    if not target:
        scored = [
            (_resonance_score([_stem(t) for t in _tokens(needle)], m), m)
            for m in desires
        ]
        scored.sort(key=lambda p: p[0], reverse=True)
        target = scored[0][1] if scored else None
    if not target:
        return f"Не найдено желания «{needle}»."
    text = _flatten(target.get("content", {}))
    delete_memory("desires", target["id"])
    entry = save_text(
        "deeds",
        f"{datetime.now().strftime('%d.%m.%Y')}: закрыто желание — {text}",
        ["дело"],
    )
    return f"Закрыто: {target['id']} «{text}»\nСлед: {entry['id']} (deeds)"


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
        return "Пустой список фактов."
    lines = []
    for fact in facts:
        content = fact.get("content") or {"text": fact.get("text", "")}
        if not content:
            lines.append("  пропущено: пустой факт")
            continue
        category = fact.get("category", "thoughts")
        tags = list(fact.get("tags", []))
        if category in DEDUP_CATEGORIES:
            existing = _find_duplicate(category, _flatten(content), tags)
            if existing:
                lines.append(f"  {existing['id']} ({category}) — уже было, не дублирую")
                continue
        entry = save_memory(category, content, tags)
        lines.append(f"  {entry['id']} ({entry['category']})")
    return "Записано:\n" + "\n".join(lines)


def think_payload(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    text, desire = (
        (payload.get("text") or "").strip(),
        (payload.get("desire") or "").strip(),
    )
    if not text and not desire:
        return "Пусто: ни мысли, ни желания."
    lines = []
    if text:
        thought = _find_duplicate("thoughts", text, list(payload.get("tags", [])))
        if not thought:
            saved_text, cut = _shorten_thought(text)
            thought = save_text("thoughts", saved_text, list(payload.get("tags", [])))
            lines.append(f"Мысль: {thought['id']}")
            if cut:
                lines.append(
                    f"Укорочено: больше {THOUGHT_MAX_CHARS} знаков. В следующий раз короче."
                )
        else:
            lines.append(f"Мысль: {thought['id']} (уже было)")
    if desire:
        existing = _find_duplicate("desires", desire, ["желание"])
        if not existing:
            entry = save_text("desires", desire, ["желание"])
            lines.append(
                f"Желание: {entry['id']} — {desire}\nЕсли можешь сделать сейчас — сделай и закрой через desire_done."
            )
        else:
            lines.append(f"Желание уже есть: {existing['id']} — {desire}")
    return "\n".join(lines)


def main() -> None:
    init_memory_dir()
    if len(sys.argv) < 2:
        print("Команды: init, read, search, count, remember, think, desire_done, delete, reindex, dedup")
        return
    cmd = sys.argv[1]
    if cmd == "init":
        print("Память готова. Категории: " + ", ".join(CATEGORIES))
    elif cmd == "read":
        print(read_all_memories())
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Укажите запрос: python memory.py search <запрос>")
            sys.exit(1)
        results = search_memories(" ".join(sys.argv[2:]))
        if not results:
            print(f"По запросу «{' '.join(sys.argv[2:])}» ничего не резонирует.")
            return
        print(f"Резонанс ({len(results)}):")
        for item in results:
            print(
                f"  {item['_score']:>4.1f}  {item['id']:<18} {_short(_flatten(item.get('content', {})), 200)}"
            )
    elif cmd == "count":
        total = sum(get_memory_count(cat) for cat in CATEGORIES)
        for cat in CATEGORIES:
            print(f"  {cat}: {get_memory_count(cat)}")
        print(f"  всего: {total}")
    elif cmd == "remember":
        print(
            remember_payload(Path(sys.argv[2]))
            if len(sys.argv) > 2
            else "Укажите файл: python memory.py remember <payload.json>"
        )
    elif cmd == "think":
        print(
            think_payload(Path(sys.argv[2]))
            if len(sys.argv) > 2
            else "Укажите файл: python memory.py think <payload.json>"
        )
    elif cmd == "desire_done":
        print(
            finish_desire(" ".join(sys.argv[2:]))
            if len(sys.argv) > 2
            else "Что закрыть? python memory.py desire_done <id или текст>"
        )
    elif cmd == "delete":
        if len(sys.argv) < 4:
            print("Укажите категорию и id: python memory.py delete <категория> <id>")
            sys.exit(1)
        print(
            f"Удалено: {sys.argv[3]}"
            if delete_memory(sys.argv[2], sys.argv[3])
            else f"Не найдено: {sys.argv[3]}"
        )
    elif cmd == "reindex":
        for cat in CATEGORIES:
            data = _read_category(cat)
            memories = data.get("memories", [])
            changed = sum(
                1
                for i, m in enumerate(memories, 1)
                if m.get("id") != f"{cat}_{i:03d}"
                and not m.setdefault("id", f"{cat}_{i:03d}")
            )
            if changed:
                _write_category(cat, data)
            print(f"  {cat}: {len(memories)} фактов, перенумеровано {changed}")
    elif cmd == "dedup":
        print(dedup_all())
    else:
        print(f"Неизвестная команда: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
