import json
import os
import glob

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def has_empty_fields(data):
    if not data:
        return True

    for key, value in data.items():
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, list) and not value:
            return True
        if isinstance(value, dict):
            if has_empty_fields(value):
                return True
    return False


# 🔹 Testlauf
if __name__ == "__main__":
    test_data = {
        "name": "Иван",
        "email": "ivan@example.com",
        "skills": ["Python", "FastAPI", "OpenAI"]
    }
    save_json(test_data, "data_output/test.json")
    print("✅ JSON сохранён в data_output/test.json")
