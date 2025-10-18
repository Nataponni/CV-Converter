import re
from tech_mapping import TECH_MAPPING


# ============================================================
# 1️⃣ Основная функция нормализации Hard Skills
# ============================================================
def remap_hard_skills(hard_skills_from_gpt):
    """
    Унифицирует и нормализует структуру hard_skills:
    - Проверяет каждое значение (dict или str)
    - Приводит имена к стандартным категориям из TECH_MAPPING
    - Удаляет дубликаты
    - Расширяет категории, если GPT вернул новые
    """

    # Базовая структура
    mapped_skills = {
        "cloud_platforms": [],
        "devops_iac": [],
        "ci_cd_tools": [],
        "containers_orchestration": [],
        "programming_languages": [],
        "databases": [],
        "backend": [],
        "frontend": [],
        "data_engineering": [],
        "etl_tools": [],
        "bi_tools": [],
        "analytics": [],
        "monitoring_security": [],
        "security": [],
        "ai_ml_tools": [],
        "infrastructure_os": [],
        "other_tools": [],
    }

    # Если GPT вернул None или не dict — выходим
    if not isinstance(hard_skills_from_gpt, dict):
        return mapped_skills

    # Проходим по всем категориям и их значениям
    for category, tools in hard_skills_from_gpt.items():
        if not isinstance(tools, list):
            continue

        for item in tools:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                years = item.get("years_experience", 0)
            else:
                name = str(item).strip()
                years = 0

            if not name:
                continue

            # Проверяем соответствие TECH_MAPPING
            matched_category = None
            for pattern, mapped_category in TECH_MAPPING.items():
                if re.search(pattern, name.lower()):
                    matched_category = mapped_category
                    break

            # Если не найдено в маппинге — помещаем в "other_tools"
            target_cat = matched_category or "other_tools"

            # Добавляем в результирующую категорию
            mapped_skills.setdefault(target_cat, []).append({
                "name": name,
                "years_experience": years
            })

    # ============================================================
    # 2️⃣ Удаление дубликатов и сортировка
    # ============================================================
    for cat, tools in mapped_skills.items():
        seen = set()
        unique_tools = []
        for tool in tools:
            key = tool["name"].strip().lower().replace(" ", "")
            if key not in seen:
                seen.add(key)
                unique_tools.append(tool)
        # Сортируем по алфавиту
        mapped_skills[cat] = sorted(unique_tools, key=lambda x: x["name"].lower())

    return mapped_skills


# ============================================================
# 🔍 Отладочный запуск
# ============================================================
if __name__ == "__main__":
    import json

    # Пример теста
    test_data = {
        "cloud_platforms": ["AWS", "Azure", "Google Cloud"],
        "ci_cd_tools": ["Jenkins", "GitLab", "Azure DevOps"],
        "programming_languages": ["Python", "C++", "JavaScript"],
        "misc": ["Nginx", "Linux"]
    }

    remapped = remap_hard_skills(test_data)
    print(json.dumps(remapped, indent=2, ensure_ascii=False))
