import os
import json
import ast
import logging
from dotenv import load_dotenv
from openai import OpenAI
from postprocess import safe_parse_if_str

# ============================================================
# 🔧 Initialisierung
# ============================================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logging.basicConfig(level=logging.INFO)

# ============================================================
# 🧠 Hauptfunktion zum Aufruf von GPT
# ============================================================
def ask_chatgpt(text, mode="details", base_structure=None, model="gpt-4o-mini"):
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
            temperature=0.1
)
        raw = response.choices[0].message.content
        return {"raw_response": raw, "mode": mode, "prompt": prompt}

    except Exception as e:
        logging.error(f"❌ GPT error: {e}")
        return {"raw_response": "", "error": str(e)}
# ============================================================
#  
# ============================================================

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

# ============================================================

def _call_gpt_and_parse(prompt: str, model: str = "gpt-4o-mini") -> dict:
    """Один GPT-вызов + безопасный разбор JSON (общий хелпер для JSON-ответов)."""
    try:
        messages = [
            {"role": "system", "content": "You are an expert CV parser."},
            {"role": "user", "content": prompt},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1
        )
        raw = response.choices[0].message.content or ""
        parsed = safe_parse_if_str(raw)
        return {"success": True, "json": parsed, "raw_response": raw}
    except Exception as e:
        logging.error(f"❌ GPT step failed: {e}")
        return {"success": False, "json": {}, "raw_response": ""}


def gpt_extract_cv_without_projects(text: str, model: str = "gpt-4o-mini") -> dict:
    """Извлекает все поля CV, кроме projects_experience (он остаётся [])."""
    prompt = f"""
TASK: Extract a structured CV JSON from the text, but DO NOT extract any projects.

INSTRUCTIONS:

- Extract a complete, structured JSON strictly following the provided SCHEMA.
- Detect the candidate’s actual domain (e.g., Cloud, DevOps, BI, Data Engineering) based on tools, project content, and terminology.
- Avoid assumptions — rely only on what's clearly stated or strongly implied in the resume.
- If a field is unknown or not present in the CV, use empty values: "" for strings, [] for lists, {{}} for objects. Do NOT guess.
- The ONLY exception: for "skills_overview.years_of_experience" you MUST infer an approximate integer value based on project durations and global statements (e.g., "5+ years").
- Do NOT wrap arrays or objects into strings. Always output proper JSON values.
- Always extract and include exact start and end dates for every project, job, or education entry.

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
  * "years_of_experience" MUST never be empty. If not explicitly stated, infer a conservative integer (e.g., 1, 2, 3, 5) from project durations or CV summary.
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
  "projects_experience": [],
  "skills_overview": [{{
    "category": "",
    "tools": [],
    "years_of_experience": ""
  }}],
  "website": ""
}}

TEXT:
{text}
"""
    return _call_gpt_and_parse(prompt, model=model)


def gpt_extract_projects_text(text: str, model: str = "gpt-4o-mini") -> dict:
    """Возвращает один большой текст с проектами, размеченный === PROJECT N ===."""
    prompt = f"""
TASK: Extract ONLY project sections from the following CV text.

INSTRUCTIONS:
- A project is a block describing work for a client, product or role, with responsibilities and usually a duration.
- Read the entire CV and isolate each distinct project.
- For each project, output in the following format:

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

CV_TEXT:
{text}
"""
    try:
        messages = [
            {"role": "system", "content": "You are an expert CV parser."},
            {"role": "user", "content": prompt},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1
        )
        raw = response.choices[0].message.content or ""
        return {"success": True, "text": raw, "raw_response": raw}
    except Exception as e:
        logging.error(f"❌ GPT projects-text step failed: {e}")
        return {"success": False, "text": "", "raw_response": ""}


def gpt_structurize_projects_from_text(projects_text: str, model: str = "gpt-4o-mini") -> dict:
    """Преобразует текст с === PROJECT N === в поле `projects_experience` целевой схемы."""
    prompt = f"""
TASK: Convert the following PROJECTS text into structured JSON objects.

INPUT FORMAT:
- The text contains multiple project blocks, each starting with a delimiter line:

=== PROJECT 1 ===
<raw project text>

=== PROJECT 2 ===
<raw project text>
...

PROJECT_SCHEMA:
{{ 
  "project_title": "",
  "overview": "",
  "role": "",
  "duration": "",
  "responsibilities": [],
  "tech_stack": []
}}

INSTRUCTIONS:
- For each input project, produce one object following PROJECT_SCHEMA.
- If the original project text is not in English (e.g. German), TRANSLATE all textual fields
  (project_title, overview, role, responsibilities, tech_stack items) to natural English.
- Preserve the meaning and level of technical detail when translating.
- Normalize duration to English format "MMM YYYY – MMM YYYY" or "MMM YYYY – Present".
- Clean any OCR noise or stray characters (e.g., "Jan 2023 nJetzt -" → "Jan 2023 – Present").
- Extract:
  - project_title in English (short, descriptive)
  - a concise overview in English (2–3 sentences)
  - role in English (e.g., "Lead BI Developer", "Data Engineer")
  - duration exactly as written in the text
  - responsibilities as English bullet-style strings (start with action verbs, max 18 words)
  - tech_stack as a flat list of tools/technologies.
- If any field is missing in the text, leave it as an empty string or empty list.
- Return ONLY JSON of the form {{ "projects_experience": [PROJECT_SCHEMA, ...]}}.

PROJECTS_TEXT:
{projects_text}
"""
    return _call_gpt_and_parse(prompt, model=model)

def run_stage_based_parsing(text: str, model: str = "gpt-4o-mini") -> dict:
    """
    Stage-based pipeline:
    1. Extract general CV info without projects
    2. Extract raw text for relevant projects
    3. Structurize the extracted project text into JSON
    4. Merge into one final result JSON
    """

    try:
        # Шаг 1: без проектов
        step1 = gpt_extract_cv_without_projects(text, model=model)
        if not step1.get("success"):
            return {"success": False, "error": "Step 1 failed: general CV info"}

        # Шаг 2: получить текст проектов
        step2 = gpt_extract_projects_text(text, model=model)
        if not step2.get("success"):
            return {"success": False, "error": "Step 2 failed: projects text"}

        # Шаг 3: превратить текст проектов в структуру
        step3 = gpt_structurize_projects_from_text(step2["text"], model=model)
        if not step3.get("success"):
            return {"success": False, "error": "Step 3 failed: project structuring"}

        # Объединение
        result_json = step1["json"]
        result_json["projects_experience"] = step3["json"].get("projects_experience", [])

        return {
            "success": True,
            "json": result_json,
            "raw_projects_text": step2["text"]
        }

    except Exception as e:
        logging.error(f"❌ Stage-based parsing pipeline failed: {e}")
        return {"success": False, "error": str(e)}

from typing import Dict, Any
def gpt_generate_text_cv_summary(cv_data: Dict[str, Any], model: str = "gpt-4o-mini") -> dict:
    """
    Generates a concise CV summary including:
    - Relevant Experience (2–5 key projects, 170–180 words total)
    - Expertise bullets (3–5 items, 30–32 words per bullet)
    - Why Me section (~40 words)
    Output is plain text. No JSON. No explanations.
    """
  # 1. Преобразуем словарь в строку для промпта
    structured_data_str = json.dumps(cv_data, ensure_ascii=False, indent=2)
    prompt = f"""
TASK: Generate a plain-text CV summary from the structured resume data below.

OUTPUT STRUCTURE:

--- RELEVANT EXPERIENCE ---
• Include exactly 2–5 projects from 'projects_experience'. No more, no less.
• Only use content from the structured 'projects_experience' field. Do not invent or summarize from other sections.
• Limit total section length to 170–180 words and 1200–1300 characters (including spaces).
• Each bullet must describe one project only: include title, duration, 1–2 key results (max 18 words each), and 2–3 main technologies.
• Do not merge multiple projects into one bullet.
• If several projects share the same date range (e.g., May 2020 – Aug 2025), group them under that date in parentheses. Then list each project as a separate bullet below. This avoids repeating the same date in each line.
• Prioritize the most relevant and unique projects. Avoid duplicates or similar entries. Focus on business value and diversity of experience (e.g., platforms, automation, observability, security).
• Ignore unimportant, redundant, or overlapping projects.

--- EXPERTISE ---
• Write 3–5 bullet points.
• Each bullet should be 28–30 words (230–250 characters including spaces).
• Focus on unique technical strengths and relevant experience (e.g., "6+ years with Terraform", "Strong CI/CD background in FinTech").
• Each point must start with a measurable or domain-relevant phrase, such as:
   - “6+ years with Python and SQL”
   - “Strong CI/CD delivery in FinTech”
   - “Hands-on MLOps with Azure DevOps and MLflow”
• Use this format consistently across all points.
• Avoid vague summaries — favor specific skills, years, or business domains.
• Each bullet must reflect a unique skillset or perspective, avoiding repetition across bullets.

--- WHY ME ---
• Write one paragraph of 35–40 words (270–290 characters including spaces).
• Clearly highlight the candidate’s unique value for the target role.
• Avoid soft skills or general motivation. Focus on differentiators: technical strengths, domains, scale of delivery, impact.

RULES:
- Use only structured resume data (especially 'projects_experience').
- Do NOT invent content or hallucinate skills, tools, or project names.
- Do NOT copy from unstructured text sections.
- Output must be plain English with no markdown, no comments, no labels.
- Style: concise, professional, high-density, no fluff.
- Output format: only plain text. No comments, no code blocks.
- Language: English.

FORMATTING:
- Separate each bullet or paragraph with a single blank line.
- Return the section headers exactly as written: --- RELEVANT EXPERIENCE ---, --- EXPERTISE ---, --- WHY ME ---.
- Each project, expertise point, and the WHY ME paragraph must be clearly separated by a blank line for readability.

STRUCTURED CV DATA:
{structured_data_str}
"""

    try:
        messages = [
            {
                "role": "system",
                "content": """
                You are a senior CV writer specialized in technical summaries. 
                Your ONLY task is to generate the summary following ALL formatting and content rules below.
                CRITICAL RULES: Use only structured data. Do not invent content. Do not use markdown.
                """
            },
            # Оставьте в prompt только структуру и переменные
            {"role": "user", "content": prompt}, 
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1
        )

        raw = response.choices[0].message.content.strip()

        return {
            "success": True,
            "output_text": raw
        }

    except Exception as e:
        logging.error(f"❌ GPT summary generation failed: {e}")
        return {
            "success": False,
            "output_text": "",
            "error": str(e)
        }
