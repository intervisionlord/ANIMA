"""Пути, категории и числовые параметры движка ANIMA."""

from pathlib import Path

# Пути считаются от корня проекта: этот файл лежит в anima/,
# поэтому родитель родителя — каталог с memory.py и synonyms.json.
ROOT = Path(__file__).parent.parent
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
