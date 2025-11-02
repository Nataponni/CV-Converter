import os
import re
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# 🔧 Инициализация
# ============================================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logging.basicConfig(level=logging.INFO)

# ============================================================
# 🧠 Основная функция вызова GPT
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
- Always extract and include exact start and end dates for every project, job, or education entry.

=== PROJECTS ===

In the "projects_experience" field:

• Always extract any block that begins with `Project:` and contains both `title:` and `duration:`.  
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
  * Always extract actual tools listed under each category in the CV, even if they appear in the same line as the category or year.
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

=== DATE FORMATTING ===
- Convert formats like:
  * "07.21 –" → "Jul 2021 – Present"
  * "07.21 – 12.23" → "Jul 2021 – Dec 2023"
  * "2020" → "Jan 2020 – Dec 2020"
  * German words like "Jetzt", "Heute", "Derzeit" → "Present"

=== OUTPUT RULES ===
- Return a single valid JSON object strictly matching the SCHEMA.
- Do NOT return markdown, explanations, comments, or prose — only JSON.
- Do NOT hallucinate tools, projects, dates, or titles.
- Do NOT change field names or structure.
- Dates must be extracted even if embedded in non-standard formats, such as:
  * PowerPoint-style bullets or slide-like phrasing
  * Freeform text, e.g., "During my MSc in 2021 I..."
  * Visual or manual formats, e.g., "07/21", "since 2020", "2020 – today"
- Always scan project descriptions, role titles, and surrounding context for implicit time references.
- If a date is mentioned indirectly (e.g., "as part of my 2022 thesis"), infer the full range logically (e.g., "Jan 2022 – Dec 2022").
  - Accept formats like:
  * "07/21", "07.21", "07-21"
  * "seit 2020", "from 2020", "during 2020"
  * "2020 – heute", "2020 – now", "2020 – aktuell"

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

    # --- собираем сообщения
    messages = [
        {"role": "system", "content": "You are an expert CV parser."},
        {"role": "user", "content": prompt},
    ]

    if mode == "details" and base_structure:
        messages.append({
            "role": "user",
            "content": f"Use this structure strictly as your schema:\n{json.dumps(base_structure, ensure_ascii=False, indent=2)}"
        })

    # --- запрос к API
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
# 🔄 Обёртки
# ============================================================
def extract_structure_with_gpt(text: str) -> dict:
    return ask_chatgpt(text, mode="structure")

def extract_details_with_gpt(text: str, structure: dict) -> dict:
    return ask_chatgpt(text, mode="details", base_structure=structure)

def auto_fix_missing_fields(data: dict) -> dict:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return ask_chatgpt(text, mode="fix")

def run_robust_cv_parsing(text: str, model="gpt-5-mini") -> dict:
    """
    Стабильный GPT-вызов с fallback логикой:
    1. Попробовать structure → details
    2. Если details упал → fix
    3. Если всё упало → моно-вызов (один этап)
    """
    try:
        logging.info("🔎 Step 1: Extract structure")
        structure_raw = ask_chatgpt(text, mode="structure")
        base_structure = json.loads(structure_raw.get("raw_response", "{}"))

        logging.info("🧠 Step 2: Extract details")
        detailed_result = ask_chatgpt(text, mode="details", base_structure=base_structure)

        try:
            parsed = json.loads(detailed_result.get("raw_response", "{}"))
            return {"success": True, "json": parsed, "raw_response": detailed_result["raw_response"], "mode": "details"}
        except json.JSONDecodeError:
            logging.warning("⚠️ Step 2 failed, trying fix...")
            fixed_result = ask_chatgpt(detailed_result.get("raw_response", "{}"), mode="fix")
            try:
                parsed_fixed = json.loads(fixed_result.get("raw_response", "{}"))
                return {"success": True, "json": parsed_fixed, "raw_response": fixed_result["raw_response"], "mode": "fix"}
            except json.JSONDecodeError:
                logging.warning("⚠️ Fix also failed, trying mono mode...")
    except Exception as e:
        logging.error(f"❌ Structured pipeline failed: {e}")

    # Mono fallback
    logging.info("🚨 Mono mode fallback")
    from chatgpt_client import ask_chatgpt as mono_mode
    result = mono_mode(text)
    if result.get("success"):
        return result
    return {"success": False, "json": {}, "raw_response": "", "mode": "fail"}


# ============================================================
# 🧪 Локальный запуск
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
            filled_json = json.loads(result["raw_response"])

            from postprocess import postprocess_filled_cv
            with open("debug/full_prepared_text.txt", "r", encoding="utf-8") as f:
                raw_text = f.read()

            filled_json = postprocess_filled_cv(filled_json, raw_text)

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