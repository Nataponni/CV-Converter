
import re

# ============================================================
# 🔍 Интеллектуальное восстановление языков
# ============================================================

def unify_languages(langs, original_text=None):
    """
    Сохраняет языки и уровни ровно как в CV.
    Не переводит уровни (B2 → Fluent), не угадывает.
    Если уровень не найден, подставляет 'Unspecified'.
    """
    normalized = []

    # 1️⃣ Обрабатываем то, что GPT вернул
    for entry in langs:
        if isinstance(entry, str):
            entry = {"language": entry, "level": ""}
        if not isinstance(entry, dict):
            continue

        lang = entry.get("language", "").strip().capitalize()
        level = entry.get("level", "").strip()

        if not level:
            level = "Unspecified"

        if lang:
            normalized.append({"language": lang, "level": level})

    # 2️⃣ Если GPT не вернул языков — пытаемся найти вручную
    if not normalized and original_text:
        text = original_text.lower()
        known_langs = [
            "english", "german", "french", "spanish", "italian",
            "russian", "polish", "czech", "portuguese", "chinese",
            "japanese", "korean", "dutch", "turkish", "swedish"
        ]

        for lang in known_langs:
            if re.search(rf"\b{lang}\b", text):
                snippet = text[max(0, text.find(lang) - 40): text.find(lang) + 60]
                match = re.search(r"\b([ABC][12]\+?|native|fluent|intermediate|upper|basic|beginner)\b", snippet, re.I)
                level = match.group(1).upper() if match else "Unspecified"
                normalized.append({"language": lang.capitalize(), "level": level})

    # 3️⃣ Убираем дубликаты
    seen = set()
    unique = []
    for item in normalized:
        key = item["language"].lower()
        if key not in seen:
            unique.append(item)
            seen.add(key)

    return unique


# ============================================================
# 2️⃣ Унификация формата дат в опыте
# ============================================================
import re
from datetime import datetime

def unify_durations(projects):
    """
    Приводит все диапазоны дат к единому виду:
    "Jul 2019 – Oct 2023" или "Jan 2021 – Present".
    Поддерживает форматы:
    - 07.19 – 10.23
    - 09/2020 – 04/2024
    - Mar 2020 – Present
    - 2020 – 2023
    - 07.2021 –
    """
    months = {
        "01": "Jan", "1": "Jan",
        "02": "Feb", "2": "Feb",
        "03": "Mar", "3": "Mar",
        "04": "Apr", "4": "Apr",
        "05": "May", "5": "May",
        "06": "Jun", "6": "Jun",
        "07": "Jul", "7": "Jul",
        "08": "Aug", "8": "Aug",
        "09": "Sep", "9": "Sep",
        "10": "Oct", "11": "Nov", "12": "Dec",
    }

    for project in projects:
        duration = project.get("duration", "")
        if not duration:
            continue

        original = duration.strip()

        # 1️⃣ Приводим дефисы и пробелы к стандарту
        duration = re.sub(r"[–—−]+", "-", duration)
        duration = re.sub(r"\s*-\s*", " - ", duration)

        # 2️⃣ Заменяем локализованные слова
        duration = re.sub(r"(?i)\b(Jetzt|Heute|Aktuell|Now)\b", "Present", duration)
        duration = re.sub(r"(?i)\b(Gegenwärtig|Momentan|Derzeit)\b", "Present", duration)

        # 3️⃣ Обрабатываем форматы вроде "07.21 - 10.23"
        m = re.match(r"^\s*(\d{1,2})[./-](\d{2,4})\s*-\s*(\d{1,2})[./-](\d{2,4}|Present)\s*$", duration)
        if m:
            start_m, start_y, end_m, end_y = m.groups()
            start_y = _normalize_year(start_y)
            end_y = "Present" if "Present" in end_y else _normalize_year(end_y)
            start = f"{months.get(start_m.zfill(2), 'Jan')} {start_y}"
            end = f"{months.get(end_m.zfill(2), 'Jan')} {end_y}"
            project["duration"] = f"{start} – {end}"
            continue

        # 4️⃣ Форматы "07.21 –" или "07.2021 –"
        m = re.match(r"^\s*(\d{1,2})[./-](\d{2,4})\s*-\s*$", duration)
        if m:
            start_m, start_y = m.groups()
            start_y = _normalize_year(start_y)
            start = f"{months.get(start_m.zfill(2), 'Jan')} {start_y}"
            project["duration"] = f"{start} – Present"
            continue

        # 5️⃣ Форматы "2019 - 2023" или "2020 - Present"
        m = re.match(r"^\s*(19|20)\d{2}\s*-\s*(?:19|20)?\d{2}|Present\s*$", duration)
        if m:
            duration = duration.replace("-", "–")
            project["duration"] = duration
            continue

        # 6️⃣ Форматы "Mar 2020 - Oct 2023"
        m = re.match(
            r"(?i)^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*\s*(?:\d{4}|Present)",
            duration,
        )
        if m:
            duration = re.sub(r"-", "–", duration)
            project["duration"] = duration.strip()
            continue

        # 7️⃣ Если ничего не сработало — восстанавливаем из overview
        if not project.get("duration"):
            overview = project.get("overview", "")
            match = re.search(r"(\b\d{4}\b).*(\b\d{4}\b|Present)", overview)
            if match:
                project["duration"] = f"{match.group(1)} – {match.group(2)}"
            else:
                project["duration"] = original.strip()

    return projects


def _normalize_year(y):
    """Помогает корректно обрабатывать 2- и 4-значные года."""
    y = y.strip()
    if len(y) == 2:
        # если 19–23 → это 2019–2023
        return f"20{y}"
    return y



# ============================================================
# 3️⃣ Удаление дубликатов из hard_skills
# ============================================================
def clean_duplicates_in_skills(skills):
    """
    Удаляет дубликаты из каждой категории hard_skills,
    сравнивая имена без регистра.
    """
    if not isinstance(skills, dict):
        return {}

    cleaned = {}
    for cat, arr in skills.items():
        if not isinstance(arr, list):
            continue

        seen = set()
        unique = []
        for item in arr:
            if isinstance(item, dict):
                name = item.get("name", "").strip().lower()
            else:
                name = str(item).strip().lower()

            if name and name not in seen:
                unique.append(item)
                seen.add(name)

        cleaned[cat] = unique

    return cleaned
