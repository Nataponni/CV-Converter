import json
import os
import tempfile
from typing import Any, Dict


# ============================================================
# 1️⃣ Безопасное сохранение JSON
# ============================================================
def save_json(filepath: str, data: Dict[str, Any]):
    """
    Безопасно сохраняет JSON в указанный путь.
    Использует атомарную запись: сначала во временный файл, потом заменяет оригинал.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="tmp_json_", suffix=".json")

    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except Exception as e:
        raise RuntimeError(f"❌ Error saving JSON to {filepath}: {e}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ============================================================
# 2️⃣ Безопасная загрузка JSON
# ============================================================
def load_json(filepath: str) -> Dict[str, Any]:
    """Загружает JSON, если он существует, иначе возвращает пустой словарь."""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"❌ Invalid JSON file: {filepath}")
    except Exception as e:
        raise RuntimeError(f"❌ Error loading JSON: {e}")


# ============================================================
# 3️⃣ Проверка пустых полей
# ============================================================
def has_empty_fields(data: Any) -> bool:
    """
    Проверяет рекурсивно, есть ли пустые строки, списки или словари.
    Возвращает True, если найдено хотя бы одно пустое поле.
    """
    if data is None:
        return True

    if isinstance(data, str):
        return not data.strip()

    if isinstance(data, (list, tuple)):
        return any(has_empty_fields(v) for v in data)

    if isinstance(data, dict):
        return any(has_empty_fields(v) for v in data.values())

    return False


# ============================================================
# 4️⃣ Подсчёт пустых полей
# ============================================================
def count_empty_fields(data: Any) -> int:
    """
    Рекурсивно считает количество пустых полей (строк, списков, словарей).
    """
    count = 0

    if data is None:
        return 1

    if isinstance(data, str):
        return 1 if not data.strip() else 0

    if isinstance(data, (list, tuple)):
        for v in data:
            count += count_empty_fields(v)
        return count

    if isinstance(data, dict):
        for v in data.values():
            count += count_empty_fields(v)
        return count

    return 0


# ============================================================
# 5️⃣ Утилиты для отладки (опционально)
# ============================================================
if __name__ == "__main__":
    test_data = {
        "name": "Manuel Wolfsgruber",
        "email": "",
        "languages": ["English", ""],
        "projects": [
            {"name": "Data Pipeline", "duration": "", "tools": ["Python", "Airflow"]},
            {},
        ],
    }

    print("Has empty fields:", has_empty_fields(test_data))
    print("Empty field count:", count_empty_fields(test_data))

    save_json("data_output/test.json", test_data)
    loaded = load_json("data_output/test.json")
    print("Loaded JSON keys:", list(loaded.keys()))
