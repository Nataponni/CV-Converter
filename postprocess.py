import re
from utils import normalize_year
from datetime import datetime


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

        # Не меняем существующий уровень
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
                # Только уровни B1–C2 или A1–B2
                match = re.search(r"\b([ABC][12]\+?)\b", snippet, re.I)
                if match:
                    level = match.group(1).upper()
                else:
                    level = "Unspecified"

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

def unify_durations(projects):
    """
    Унифицирует формат длительности проектов, сохраняя реальные даты и порядок.
    Поддерживает:
      - "07.21 – 12.23"
      - "07.2021 – Jetzt"
      - "2020 – 2023"
      - "Jan 2021 – Present"
      - "07.21 –"
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
        duration = original

        # --- Normalize spacing and dashes ---
        duration = re.sub(r"[–—−]+", "-", duration)
        duration = re.sub(r"\s*-\s*", " - ", duration)

        # --- Normalize localized terms ---
        duration = re.sub(r"(?i)\b(Jetzt|Heute|Aktuell|Now|Present|Gegenwärtig|Momentan|Derzeit)\b", "Present", duration)

        # --- 1️⃣ Format "07.21 - 10.23" ---
        m = re.match(r"^\s*(\d{1,2})[./-](\d{2,4})\s*-\s*(\d{1,2})[./-](\d{2,4}|Present)\s*$", duration)
        if m:
            start_m, start_y, end_m, end_y = m.groups()
            start_y = normalize_year(start_y)
            end_y = "Present" if "Present" in end_y else normalize_year(end_y)
            start = f"{months.get(start_m.zfill(2), 'Jan')} {start_y}"
            end = f"{months.get(end_m.zfill(2), 'Jan')} {end_y}"
            project["duration"] = f"{start} – {end}"
            continue

        # --- 2️⃣ Format "07.21 –" ---
        m = re.match(r"^\s*(\d{1,2})[./-](\d{2,4})\s*-\s*$", duration)
        if m:
            start_m, start_y = m.groups()
            start_y = normalize_year(start_y)
            start = f"{months.get(start_m.zfill(2), 'Jan')} {start_y}"
            project["duration"] = f"{start} – Present"
            continue

        # --- 3️⃣ Format "2019 - 2023" ---
        m = re.match(r"^\s*((19|20)\d{2})\s*-\s*((?:19|20)?\d{2}|Present)\s*$", duration)
        if m:
            start_y, _, end_y = m.groups()
            if len(end_y) == 2:
                end_y = "20" + end_y
            if int(start_y) > int(end_y.replace("Present", str(datetime.now().year))):
                # swap if reversed
                start_y, end_y = end_y, start_y
            project["duration"] = f"{start_y} – {end_y}"
            continue

        # --- 4️⃣ "Mar 2020 - Oct 2023" ---
        m = re.match(
            r"(?i)^\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*\s*(?:\d{4}|Present)",
            duration,
        )
        if m:
            duration = re.sub(r"-", "–", duration)
            project["duration"] = duration.strip()
            continue

        # --- 5️⃣ Try to recover from overview if GPT skipped it ---
        overview = project.get("overview", "")
        match = re.search(r"(\b\d{4}\b).{0,20}?(\b\d{4}\b|Present)", overview)
        if match:
            y1, y2 = match.groups()
            if y1 and y2:
                if int(y1) > int(y2.replace("Present", str(datetime.now().year))):
                    y1, y2 = y2, y1
                project["duration"] = f"{y1} – {y2}"
                continue

        # --- 6️⃣ Fallback: one year found ---
        match = re.search(r"\b(19|20)\d{2}\b", original)
        if match and not project.get("duration"):
            project["duration"] = f"{match.group(0)} – Present"

    return projects



# ============================================================
# 3️⃣ Удаление дубликатов из hard_skills
# ============================================================
def clean_duplicates_in_skills(skills):
    """Удаляет дубликаты из каждой категории hard_skills."""
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

def fix_project_dates_from_text(projects, original_text):
    """
    Восстанавливает реальные даты (start-end) проектов на основе исходного PDF-текста.
    Если GPT пропустил даты, берёт их из текста по шаблонам:
    - 07.2019 – 12.2021
    - 09/2020 – 04/2024
    - 2020 – Present
    """
    if not projects or not original_text:
        return projects

    text = original_text
    date_pattern = re.compile(
        r"(\d{2}[./]\d{2,4})\s*[–-]\s*(\d{2}[./]\d{2,4}|Present|Jetzt|Heute|Aktuell)",
        flags=re.IGNORECASE
    )
    year_pattern = re.compile(
        r"(\b(19|20)\d{2}\b)\s*[–-]\s*((?:19|20)?\d{2}|Present|Jetzt|Heute|Aktuell)",
        flags=re.IGNORECASE
    )

    found_dates = date_pattern.findall(text) + year_pattern.findall(text)

    def normalize_date(raw):
        raw = raw.replace("/", ".")
        raw = re.sub(r"(?i)(Jetzt|Heute|Aktuell)", "Present", raw)
        return raw.strip()

    # Список всех найденных диапазонов из текста
    ranges = [f"{normalize_date(m[0])} – {normalize_date(m[1])}" if len(m) > 1 else "" for m in found_dates]

    # Присваиваем их проектам (если duration пустой)
    for i, proj in enumerate(projects):
        if not proj.get("duration") or proj["duration"].lower() in ["present", ""]:
            if i < len(ranges):
                proj["duration"] = ranges[i]

    return projects
