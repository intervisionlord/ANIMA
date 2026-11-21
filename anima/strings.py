"""Пользовательские тексты ANIMA: подсказки CLI, заголовки и сообщения.

Все строки — шаблоны с именованными плейсхолдерами для ``str.format``.
Так тексты правятся в одном месте и не перемешаны с логикой.
"""

# Ошибки и статусы
MSG_UNKNOWN_CATEGORY = "Неизвестная категория: {category}"
MSG_MEMORY_EMPTY = "Память пуста. Это начало."
MSG_NO_DESIRES = "Незакрытых желаний нет."
MSG_DESIRE_NOT_FOUND = "Не найдено желания «{needle}»."
MSG_DELETED = "Удалено: {id}"
MSG_NOT_FOUND = "Не найдено: {id}"
CLI_UNKNOWN_CMD = "Неизвестная команда: {cmd}"

# Дедупликация
MSG_DEDUP_HEADER = "Почищено:"
MSG_DEDUP_REMOVED = "  {category}: удалено дублей — {removed}"
MSG_DEDUP_NONE = "Дублей не нашлось."

# Чтение памяти
HEADER_DESIRES = "ЧЕГО ХОЧУ (ещё не сделано):"
LINE_DESIRE = "  {id}  {text}"
HEADER_CATEGORY = "--- {cat} · {title} ({count}) ---"
LINE_MEMORY = "  {id} [{date}] {text}"

# Желания и дела
MSG_DESIRE_CLOSED = "Закрыто: {id} «{text}»\nСлед: {trace_id} (deeds)"
DESIRE_DEED_TEXT = "{date}: закрыто желание — {text}"
MSG_DESIRE_SAVED = (
    "Желание: {id} — {desire}\n"
    "Если можешь сделать сейчас — сделай и закрой через desire_done."
)
MSG_DESIRE_EXISTS = "Желание уже есть: {id} — {desire}"
TAG_DEED = "дело"
TAG_DESIRE = "желание"

# Запись фактов
MSG_REMEMBER_HEADER = "Записано:"
MSG_EMPTY_FACTS = "Пустой список фактов."
MSG_FACT_SKIPPED = "  пропущено: пустой факт"
MSG_FACT_DUPLICATE = "  {id} ({category}) — уже было, не дублирую"
MSG_FACT_SAVED = "  {id} ({category})"

# Мысли
MSG_THINK_EMPTY = "Пусто: ни мысли, ни желания."
MSG_THOUGHT = "Мысль: {id}"
MSG_THOUGHT_DUPLICATE = "Мысль: {id} (уже было)"
MSG_THOUGHT_SHORTENED = "Укорочено: больше {limit} знаков. В следующий раз короче."

# Поиск
MSG_SEARCH_NONE = "По запросу «{query}» ничего не резонирует."
CLI_RESULTS_HEADER = "Резонанс ({count}):"
CLI_RESULT_LINE = "  {score:>4.1f}  {id:<18} {text}"

# CLI
CLI_COMMANDS = (
    "Команды: init, read, search, count, remember, think, "
    "desire_done, delete, reindex, dedup"
)
CLI_INIT = "Память готова. Категории: {categories}"
CLI_SEARCH_HINT = "Укажите запрос: python memory.py search <запрос>"
CLI_COUNT_LINE = "  {cat}: {count}"
CLI_COUNT_TOTAL = "  всего: {total}"
CLI_REMEMBER_HINT = "Укажите файл: python memory.py remember <payload.json>"
CLI_THINK_HINT = "Укажите файл: python memory.py think <payload.json>"
CLI_DESIRE_HINT = "Что закрыть? python memory.py desire_done <id или текст>"
CLI_DELETE_HINT = "Укажите категорию и id: python memory.py delete <категория> <id>"
CLI_REINDEX_LINE = "  {cat}: {count} фактов, перенумеровано {changed}"
