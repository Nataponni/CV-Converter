import os
import re
import json
import ast
import logging
from dotenv import load_dotenv
from openai import OpenAI
from postprocess import safe_parse_if_str, postprocess_filled_cv

# ============================================================
# 🔧 Initialisierung
# ============================================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logging.basicConfig(level=logging.INFO)

# ============================================================
# 🧠 Hauptfunktion zum Aufruf von GPT
# ============================================================
def ask_chatgpt(text, mode="details", base_structure=None, model="gpt-5-mini"):
    """
    Универсальная функция вызова GPT для CV-парсинга.
    Поддерживает режимы:
    - structure: выводит структуру JSON
    - details: извлекает все поля из текста
    - fix: заполняет пустые поля
    """
    if mode == "structure":
        task_description = "Extract only the structural JSON skeleton of the CV with all field names but empty values."
    elif mode == "fix":
        task_description = "Repair missing or empty fields logically, keeping the schema intact."
    else:
        task_description = "Extract structured CV data from text and return strictly formatted JSON only."

    prompt = f"""
TASK: {task_description}

INSTRUCTIONS:

- Extract a complete, structured JSON strictly following the provided SCHEMA.
- Detect the candidate’s actual domain (e.g., Cloud, DevOps, BI, Data Engineering) based on tools, project content, and terminology.
- Avoid assumptions — rely only on what's clearly stated or strongly implied in the resume.
- If a field is unknown or not present in the CV, use empty values: "" for strings, [] for lists, {{}} for objects. Do NOT guess.
- Do NOT wrap arrays or objects into strings. Always output proper JSON values.
- Always extract and include exact start and end dates for every project, job, or education entry.

=== PROJECTS ===

In the "projects_experience" field:

• Extract any block that contains at least a `project_title:` — even if duration is missing.
  → These blocks are always valid. Extract them even if role, overview, or tech_stack are missing. Fill missing fields with empty values.
• Preserve the full "duration" exactly as written (e.g., "Jul 2021 – Present"). Do not modify, translate, or guess.
• Extract only real, distinct projects. Use visual or semantic separation as an indicator (headings, date blocks, project keywords, client names, etc.).
• Use concise, technical bullet points (≤18 words) for "responsibilities", starting with action verbs (e.g., Designed, Built, Automated, Integrated).
• Do not split a single job into multiple projects unless:
  - It has distinct durations, OR
  - There is clear formatting separation.

• If multiple roles or tasks are grouped under the same company and duration, treat them as one project.
• Do not skip projects just because some fields are missing. If it's a valid block (with `Project:` + `title:` + `duration:`), extract it fully with empty fields where needed.
• All extracted projects must follow the schema strictly.

- NEVER wrap JSON arrays or objects in strings.
  * For example, do NOT return: "projects_experience": "[{...}]"
  * Instead, return a proper JSON list: "projects_experience": [{...}]
- Do NOT return lists as strings. Fields like "projects_experience", "skills_overview", and "languages" must be actual JSON arrays — not strings that look like lists.
- Always use double quotes for all keys and string values.
• Each distinct project must become a separate JSON object in the "projects_experience" list.
• Never merge or combine projects — even if company or technologies overlap.
• Use clear separators such as '=== PROJECT START ===' or 'Project:' to distinguish them.


  === SKILLS ===
- For "hard_skills" and "skills_overview":
  * Use ONLY these fixed categories:
    cloud_platforms, devops_iac, monitoring_security, programming_languages,
    containers_orchestration, ci_cd_tools, ai_ml_tools, databases,
    backend, frontend, security, data_engineering, etl_tools, bi_tools,
    analytics, infrastructure_os, other_tools

  * Do NOT merge or invent new categories like "BI / Analytics" — always split correctly.
  * Each tool must be placed in only ONE most relevant category.
  * Tools like "Git", "Excel", "Outlook", "Power Platform" — only use "other_tools" if nothing else fits.
  * Avoid mixing tools in one item (e.g., don't write "Python / SQL" — create separate entries).

- For "skills_overview":
  * Include all tools used in projects or summary.
  * Estimate approximate "years_of_experience" logically (e.g., from project durations or global statements like "5+ years with Azure").
  * Output must include ≥10 distinct categories.
  * Each row must follow this format: {{ "category": "", "tools": [], "years_of_experience": "" }}
  • Extract any block that contains at least a `project_title:` — even if duration is missing.
  → If duration missing, return it as an empty string "".

  * Do not leave "tools" empty — extract at least one tool per category if mentioned anywhere in the CV.

=== PROFILE SUMMARY ===
- Write a technical, third-person summary (80–100 words) describing actual domains, tools, and strengths.
- Align this summary strictly with real CV content — don't invent.

=== LANGUAGES ===
- Extract only explicitly mentioned languages and their levels (e.g., "German: native", "English: C1").
- Recognize section titles such as "Languages", "Language Skills", "Sprachen", or "Sprachkenntnisse".
- Do NOT infer any languages that are not explicitly written in the CV.
- Detect levels written as “native”, “fluent”, “C2”, “B1”, etc.
- If no languages are mentioned, return an empty list: []
- Output format:
  "languages": [
      {{"language": "German", "level": "C2"}},
      {{"language": "English", "level": "C1"}}
  ]

=== OUTPUT RULES ===
- Return a single valid JSON object strictly matching the SCHEMA.
- Do NOT return markdown, explanations, comments, or prose — only JSON.
- Do NOT hallucinate tools, projects, dates, or titles.
- Do NOT change field names or structure.
- Dates must be copied exactly as in the source (no reformatting, no translation). If unclear or not present, leave empty.

SCHEMA:
{{
  "full_name": "",
  "title": "",
  "education": "",
  "languages": [{{"language": "", "level": ""}}],
  "domains": [],
  "profile_summary": "",
  "hard_skills": {{
    "programming_languages": [],
    "backend": [],
    "frontend": [],
    "databases": [],
    "data_engineering": [],
    "etl_tools": [],
    "bi_tools": [],
    "analytics": [],
    "cloud_platforms": [],
    "devops_iac": [],
    "ci_cd_tools": [],
    "containers_orchestration": [],
    "monitoring_security": [],
    "security": [],
    "ai_ml_tools": [],
    "infrastructure_os": [],
    "other_tools": []
  }},
  "projects_experience": [
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
      "tools": [],
      "years_of_experience": ""
    }}
  ],
  "website": ""
}}

TEXT:
{text}
"""

# --- Erstellen der Nachrichten
    messages = [
        {"role": "system", "content": "You are an expert CV parser."},
        {"role": "user", "content": prompt},
    ]

    if mode == "details" and base_structure:
        messages.append({
            "role": "user",
            "content": f"Use this structure strictly as your schema:\n{json.dumps(base_structure, ensure_ascii=False, indent=2)}"
        })

# --- API-Aufruf
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        raw = response.choices[0].message.content
        return {"raw_response": raw, "mode": mode, "prompt": prompt}

    except Exception as e:
        logging.error(f"❌ GPT error: {e}")
        return {"raw_response": "", "error": str(e)}

# ============================================================
# 🔄 Wrapper-Funktionen
# ============================================================
def extract_structure_with_gpt(text: str) -> dict:
    return ask_chatgpt(text, mode="structure")

def extract_details_with_gpt(text: str, structure: dict) -> dict:
    return ask_chatgpt(text, mode="details", base_structure=structure)

def auto_fix_missing_fields(data: dict) -> dict:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return ask_chatgpt(text, mode="fix")

def safe_json_parse(raw):
    """
    Безопасно преобразует строку или объект в Python-словарь.
    Если строка содержит JSON внутри строки (например "[{...}]"),
    корректно разворачивает его.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str):
        return {}

    try:
        # 🧠 Пробуем обычный JSON
        return json.loads(raw)
    except json.JSONDecodeError:
        # 🧩 Иногда GPT использует одинарные кавычки
        try:
            return json.loads(raw.replace("'", '"'))
        except Exception:
            pass
        # 🧩 Иногда строка — это Python-представление
        try:
            return ast.literal_eval(raw)
        except Exception as e:
            logging.warning(f"⚠️ safe_json_parse failed: {e}")
            return {}

def run_robust_cv_parsing(text: str, model="gpt-5-mini") -> dict:
    """
    Stabiler GPT-Aufruf mit Fallback-Logik:
    1. Versuche zuerst structure → details
    2. Wenn details fehlschlägt → fix
    3. Wenn alles fehlschlägt → Mono-Aufruf (einzelner Schritt)
    """
    try:
        result = ask_chatgpt(text, model)
        raw_response = result.get("raw_response", "")
        parsed = safe_parse_if_str(raw_response)

        parsed["projects_experience"] = safe_parse_if_str(parsed.get("projects_experience"))
        parsed["skills_overview"] = safe_parse_if_str(parsed.get("skills_overview"))
        parsed["languages"] = safe_parse_if_str(parsed.get("languages"))

        return {
            "success": True,
            "json": parsed,
            "raw_response": raw_response,
        }

    except Exception as e:
        logging.error(f"❌ Parsing failed: {e}")
        return {"success": False, "json": {}, "raw_response": ""}
    
# ============================================================
# 🧪 Lokaler Testlauf
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    input_path = "debug/full_prepared_text.txt"
    output_path = "debug/filled_cv_from_gpt.json"

    if not os.path.exists(input_path):
        logging.warning(f"⚠️ File not found: {input_path}")
        exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        input_text = f.read()

    logging.info("📨 Sending text to GPT (mode='details')...")
    structure_raw = ask_chatgpt(input_text, mode="structure")

    try:
        base_structure = json.loads(structure_raw["raw_response"])
    except Exception:
        base_structure = None

    result = ask_chatgpt(input_text, mode="details", base_structure=base_structure)

    if "raw_response" in result:
        try:
            print("\nSTEP 1️⃣  RAW GPT RESPONSE:\n", result.get("raw_response")[:2000])
            filled_json = safe_json_parse(result["raw_response"])
            print("\nSTEP 2️⃣  AFTER safe_json_parse:\n", type(filled_json.get("projects_experience")), len(str(filled_json.get("projects_experience"))))

            with open("debug/full_prepared_text.txt", "r", encoding="utf-8") as f:
                raw_text = f.read()

            filled_json["projects_experience"] = safe_parse_if_str(filled_json.get("projects_experience"))
            print("\nSTEP 3️⃣  AFTER safe_parse_if_str:\n", type(filled_json.get("projects_experience")), len(filled_json.get("projects_experience", [])))

            filled_json["skills_overview"] = safe_parse_if_str(filled_json.get("skills_overview"))

            filled_json = postprocess_filled_cv(filled_json, raw_text)
            print("\nSTEP 3️⃣  AFTER safe_parse_if_str:\n", type(filled_json.get("projects_experience")), len(filled_json.get("projects_experience", [])))
            
            with open(output_path, "w", encoding="utf-8") as out_f:
                json.dump(filled_json, out_f, indent=2, ensure_ascii=False)

            logging.info(f"✅ Результат сохранён: {output_path}")

        except json.JSONDecodeError as e:
            logging.error("❌ JSON parsing error:")
            logging.error(e)
            logging.warning("⚠️ GPT response:")
            print(result["raw_response"])
    else:
        logging.error("❌ GPT did not return a valid response.")