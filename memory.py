"""ANIMA — точка входа CLI. Вызывается плагином memory-tools."""

import sys
from pathlib import Path

from anima import strings as S
from anima.constants import CATEGORIES
from anima.ops import (
    dedup_all,
    finish_desire,
    get_memory_count,
    read_all_memories,
    remember_payload,
    think_payload,
)
from anima.resonance import _flatten, _short, search_memories
from anima.storage import (
    _read_category,
    _write_category,
    delete_memory,
    init_memory_dir,
)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> None:
    init_memory_dir()
    if len(sys.argv) < 2:
        print(S.CLI_COMMANDS)
        return
    cmd = sys.argv[1]
    if cmd == "init":
        print(S.CLI_INIT.format(categories=", ".join(CATEGORIES)))
    elif cmd == "read":
        print(read_all_memories())
    elif cmd == "search":
        if len(sys.argv) < 3:
            print(S.CLI_SEARCH_HINT)
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search_memories(query)
        if not results:
            print(S.MSG_SEARCH_NONE.format(query=query))
            return
        print(S.CLI_RESULTS_HEADER.format(count=len(results)))
        for item in results:
            print(
                S.CLI_RESULT_LINE.format(
                    score=item["_score"],
                    id=item["id"],
                    text=_short(_flatten(item.get("content", {})), 200),
                )
            )
    elif cmd == "count":
        total = sum(get_memory_count(cat) for cat in CATEGORIES)
        for cat in CATEGORIES:
            print(S.CLI_COUNT_LINE.format(cat=cat, count=get_memory_count(cat)))
        print(S.CLI_COUNT_TOTAL.format(total=total))
    elif cmd == "remember":
        print(
            remember_payload(Path(sys.argv[2]))
            if len(sys.argv) > 2
            else S.CLI_REMEMBER_HINT
        )
    elif cmd == "think":
        print(
            think_payload(Path(sys.argv[2]))
            if len(sys.argv) > 2
            else S.CLI_THINK_HINT
        )
    elif cmd == "desire_done":
        print(
            finish_desire(" ".join(sys.argv[2:]))
            if len(sys.argv) > 2
            else S.CLI_DESIRE_HINT
        )
    elif cmd == "delete":
        if len(sys.argv) < 4:
            print(S.CLI_DELETE_HINT)
            sys.exit(1)
        print(
            S.MSG_DELETED.format(id=sys.argv[3])
            if delete_memory(sys.argv[2], sys.argv[3])
            else S.MSG_NOT_FOUND.format(id=sys.argv[3])
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
            print(
                S.CLI_REINDEX_LINE.format(
                    cat=cat, count=len(memories), changed=changed
                )
            )
    elif cmd == "dedup":
        print(dedup_all())
    else:
        print(S.CLI_UNKNOWN_CMD.format(cmd=cmd))
        sys.exit(1)


if __name__ == "__main__":
    main()
