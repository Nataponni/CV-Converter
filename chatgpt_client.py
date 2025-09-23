from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_chatgpt(text):
    prompt = f"""
        Extrahiere die Daten aus dem Text und gib JSON genau in diesem Format zurück:

    {{
    "full_name": "",
    "title": "",
    "education": "",
    "languages": [
        {{"language": "", "level": ""}}
    ],
    "domains": [],
    "profile_summary": "",
    "hard_skills": {{
        "backend": [],
        "frontend": [],
        "devops": [],
        "programming_languages": [],
        "frameworks": [],
        "databases": [],
        "cloud_platforms": [],
        "ai_ml_tools": [],
        "monitoring_security": [],
        "containers_orchestration": [],
        "ci_cd_tools": [],
        "other_tools": []
    }},
    "projects": [
        {{
        "project_title": "",
        "overview": "",
        "role": "",
        "duration": "",
        "responsibilities": [],
        "tech_stack": []
        }}
    ],
    "skills_overview": [
        {{
        "category": "",
        "tool": "",
        "years_of_experience": ""
        }}
    ],
    "website": ""
    }}

    Text:
    {text[:800]}
    """

    response = client.chat.completions.create(
        model="gpt-5-mini-2025-08-07",
        messages=[
            {"role": "system", "content": "Du gibst immer nur JSON zurück."},
            {"role": "user", "content": prompt}
        ],
        # max_completion_tokens=200
    )

    content = response.choices[0].message.content.strip()
    print(f"\n📥 Raw response repr(): {repr(content)}")

    # Tokens für Kostenkontrolle       
    usage = response.usage
    print(f"\nTokens: Eingabe={usage.prompt_tokens}, Ausgabe={usage.completion_tokens}, Gesamt={usage.total_tokens}")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": content}

# 🔹 Testlauf
if __name__ == "__main__":
    test_text = "Name: Ivan Ivanov, Email: ivan@example.com, Telefon: +49123456789"
    result = ask_chatgpt(test_text)
    print("\n🤖 Antwort von ChatGPT:\n")
    print(result)
