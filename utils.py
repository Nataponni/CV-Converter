import json
import os

def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# 🔹 Testlauf
if __name__ == "__main__":
    test_data = {
        "name": "Иван",
        "email": "ivan@example.com",
        "skills": ["Python", "FastAPI", "OpenAI"]
    }
    save_json(test_data, "data_output/test.json")
    print("✅ JSON сохранён в data_output/test.json")
