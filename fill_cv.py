import json
from utils import has_empty_fields
from chatgpt_client import ask_chatgpt


# ============================================================
# 1️⃣ Автоматическое заполнение пустых полей через GPT
# ============================================================
def auto_fill_with_gpt(data: dict) -> dict:
    """
    Использует GPT для логического заполнения пустых или отсутствующих полей.
    Работает в связке с chatgpt_client.ask_chatgpt(mode="fix").
    """
    try:
        filled = ask_chatgpt(data, mode="fix")
        if isinstance(filled, dict):
            return filled
        return data
    except Exception:
        # fallback на ручное восстановление
        return fill_missing_fields(data)


# ============================================================
# 2️⃣ Локальный (fallback) режим заполнения пропусков
# ============================================================
def fill_missing_fields(data, prefix=""):
    """
    Рекурсивно проходит по JSON и добавляет заглушки для пустых полей.
    Используется как fallback, если GPT не доступен.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}{key}"
            if isinstance(value, str) and value.strip() == "":
                data[key] = _default_value_for_key(key)
            elif isinstance(value, list):
                if not value:
                    data[key] = []
                else:
                    for i, item in enumerate(value):
                        fill_missing_fields(item, prefix=f"{full_key}[{i}].")
            elif isinstance(value, dict):
                fill_missing_fields(value, prefix=f"{full_key}.")
    return data


# ============================================================
# 3️⃣ Определение дефолтных значений
# ============================================================
def _default_value_for_key(key: str):
    """
    Возвращает дефолтное значение для поля на основе имени.
    """
    key_lower = key.lower()
    if "name" in key_lower:
        return "Unknown"
    if "title" in key_lower:
        return "Specialist"
    if "education" in key_lower:
        return "Not specified"
    if "language" in key_lower:
        return []
    if "domain" in key_lower:
        return []
    if "summary" in key_lower:
        return "No profile summary available."
    if "skills" in key_lower:
        return {}
    if "projects" in key_lower:
        return []
    if "website" in key_lower:
        return ""
    return ""


# ============================================================
# 4️⃣ Главная точка запуска
# ============================================================
def fill_cv_data(data: dict) -> dict:
    """
    Проверяет наличие пропусков и заполняет их.
    Если GPT доступен — используется auto_fill_with_gpt,
    иначе fallback на локальное заполнение.
    """
    if not has_empty_fields(data):
        return data

    try:
        return auto_fill_with_gpt(data)
    except Exception:
        return fill_missing_fields(data)

def fix_project_dates_from_text(projects, original_text):
    """
    Если GPT ошибся в годах, пытаемся восстановить реальные даты из исходного текста.
    """
    for p in projects:
        title = p.get("project_title", "")
        duration = p.get("duration", "")
        if not title:
            continue

        # Ищем рядом с названием проекта возможные даты
        pattern = rf"{re.escape(title)}.*?(\b\d{{4}}\b).*?(\b\d{{4}}\b|Present)"
        match = re.search(pattern, original_text, re.I | re.S)
        if match:
            real_dur = f"{match.group(1)} – {match.group(2)}"
            if real_dur != duration:
                p["duration"] = real_dur
    return projects

# ============================================================
# 🔍 Тестовый запуск
# ============================================================
if __name__ == "__main__":
    test_data = {
        "full_name": "Manuel Wolfsgruber",
        "title": "",
        "education": "",
        "languages": [{"language": "", "level": ""}],
        "domains": [],
        "profile_summary": "",
        "hard_skills": {"cloud_platforms": [], "programming_languages": []},
        "projects_experience": [],
        "skills_overview": [],
        "website": ""
    }

    print("Before filling:")
    print(json.dumps(test_data, indent=2, ensure_ascii=False))

    filled = fill_cv_data(test_data)

    print("\nAfter filling:")
    print(json.dumps(filled, indent=2, ensure_ascii=False))
