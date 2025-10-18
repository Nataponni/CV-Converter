import os
import re
import json
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# 🔧 Инициализация
# ============================================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ============================================================
# 🧠 Основная функция вызова GPT
# ============================================================
def ask_chatgpt(text, mode="details", base_structure=None):
    """
    Универсальная функция для работы с GPT.
    Поддерживает три режима:
    - mode="structure" → извлекает структуру CV (skeleton)
    - mode="details"   → заполняет структуру данными
    - mode="fix"       → исправляет/дополняет пропуски в JSON

    Вся логика промпта сохранена 1:1 из оригинальной версии.
    """

    # ============================================================
    # 🧩 Формируем инструкцию на основе режима
    # ============================================================
    if mode == "structure":
        task_description = "Extract only the structural JSON skeleton of the CV with all field names but empty values."
    elif mode == "fix":
        task_description = "Repair missing or empty fields logically, keeping the schema intact."
    else:
        task_description = "Extract structured data from the input text (CV, PDF text) and return ONLY JSON according to the schema."

    # ============================================================
    # 📜 Твой оригинальный промпт (полностью сохранён)
    # ============================================================
    prompt = f"""
TASK: {task_description}

INSTRUCTIONS:
- In "projects_experience":
  * Extract **all** distinct project, employment, or consulting entries mentioned in the CV — there is **no limit** on the number of projects.
    Include entries even if they belong to the same employer or overlap in time.
  * Always extract "duration" — include any dates, years, or ranges (e.g., "Jan 2022 – May 2024", "2021 – Present").
    Never leave it empty; if missing, infer approximate ranges from context or chronology.
  * Extract "responsibilities" as short, factual bullet points (max 12 words each),
    preserving original action verbs (e.g., "implemented", "designed", "deployed", "optimized").
    Remove filler phrases such as "responsible for", "helped to", "involved in".
  * Include **up to 6–8 bullet points per project**, prioritizing the most technical, leadership, or high-impact activities.
  * If multiple projects share time ranges or overlap, still repeat full durations.
    Do not merge overlapping or related projects — list each one separately if they mention
    different clients, employers, or technical focuses.
  * Retain all explicit client or employer names if mentioned.

- Extract values only if they clearly appear or are strongly implied in the text.
- If the document language is clearly English, set:
  "languages": [{{"language": "English", "level": "Fluent"}}].

- Do not invent data, but infer when the context is strong
  (e.g. English-language university → "English"; AWS, Terraform, Jenkins → "Cloud" + "DevOps" domains).

- For list-type fields (skills, tools, domains, languages):
  * Keep items unique (no duplicates).
  * Include all explicitly mentioned or clearly implied tools.
  * Use consistent categorization according to TECH_MAPPING
    (e.g. Terraform → devops_iac, Datadog → monitoring_security).
  * For "hard_skills", keep 5–8 representative items per category when available.

- When years of experience are mentioned globally
  (e.g. "8 years in IT", "5+ years with AWS"),
  propagate approximate values into related tools or categories
  (e.g. AWS → 5, Terraform → 5, CI/CD → 8).

- Use the following fixed skill categories under "hard_skills":
  cloud_platforms, devops_iac, monitoring_security, programming_languages,
  containers_orchestration, ci_cd_tools, ai_ml_tools, databases,
  backend, frontend, security, other_tools.

- If a value is missing or uncertain — return "" or [].
- Always output a fully populated JSON object following the schema exactly.
- Output must be valid JSON only — no markdown, no comments, no prose.

- "profile_summary":
  Must be a rich, technical, multi-sentence paragraph (80–100 words)
  summarizing cloud, DevOps, IaC, CI/CD, security, monitoring, automation and leadership experience.
  Use formal tone, third person, and concise phrasing.

- "skills_overview":
  Must always contain at least 10 categories, including Cloud, IaC, Containers, Orchestration,
  CI/CD, Monitoring, Databases, Security, Programming, and OS/Infrastructure.
  Each row should show the most relevant tools and their approximate years of experience (YoE).

- In "projects_experience.tech_stack":
  Include the most relevant 10–15 technologies in priority order:
  AWS, Azure, GCP, Terraform, Docker, Kubernetes, Jenkins, GitLab, Ansible, Linux.
  Do not truncate unless the text contains >12 items.

  - In "hard_skills", prefer completeness over brevity:
  include all explicitly or implicitly mentioned tools (5–10 per category).

- When you detect any date ranges (e.g. "07.21 – 12.23", "Jan 2022 - May 2024"),
  always extract them **exactly as written in the text**.
  However:
    * If the range uses European numeric format (e.g. "07.21 – 12.23"), 
      convert each month number to its English month abbreviation 
      (e.g. "Jul 2021 – Dec 2023").
    * If a range ends with a dash ("–" or "-") but has no explicit end date, 
      complete it with "Present" (e.g. "07.21 –" → "Jul 2021 – Present").
    * If you see any of the words "Jetzt", "Heute", "Aktuell", "Gegenwärtig", or "Derzeit", 
      interpret them as "Present".
    * If a single year is written (e.g. "2020"), treat it as "Jan 2020 – Dec 2020".
  Always put the full, explicit range into the "duration" field of the corresponding project.
  Never omit, shorten, or modify the range beyond these conversions.
  Always include both start and end dates.
  Always prefer the most precise date range if multiple forms appear.

Return all projects as a JSON array under the key "projects_experience".
Never truncate the list even if it’s long.
If more than 20 projects exist, include them all.


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
      "tool": "",
      "years_of_experience": ""
    }}
  ],
  "website": ""
}}

TEXT:
{text}
"""

    # ============================================================
    # 🔄 Если mode=details и есть готовая структура — добавляем
    # ============================================================
    if mode == "details" and base_structure:
        prompt += f"\n\nBASE STRUCTURE:\n{json.dumps(base_structure, ensure_ascii=False, indent=2)}"

    # ============================================================
    # ⚙️ Вызов GPT
    # ============================================================
    response = client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You must extract structured data and return only JSON. Follow the schema exactly."},
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": content}


# ============================================================
# 🧩 Исправление открытых диапазонов дат
# ============================================================
def fix_open_date_ranges(text_or_json):
    """Fixes incomplete date ranges like '07.20 –' → 'Jul 2020 – Present'."""
    if isinstance(text_or_json, dict):
        for key, value in text_or_json.items():
            if isinstance(value, dict):
                fix_open_date_ranges(value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        fix_open_date_ranges(item)
                    elif isinstance(item, str):
                        text_or_json[key][i] = fix_open_date_ranges(item)
            elif key.lower() == "duration" and isinstance(value, str):
                text_or_json[key] = fix_open_date_ranges(value)
        return text_or_json

    text = str(text_or_json)
    text = re.sub(r"\b0?1\.?(\d{2})\b", r"Jan 20\1", text)
    text = re.sub(r"\b0?2\.?(\d{2})\b", r"Feb 20\1", text)
    text = re.sub(r"\b0?3\.?(\d{2})\b", r"Mar 20\1", text)
    text = re.sub(r"\b0?4\.?(\d{2})\b", r"Apr 20\1", text)
    text = re.sub(r"\b0?5\.?(\d{2})\b", r"May 20\1", text)
    text = re.sub(r"\b0?6\.?(\d{2})\b", r"Jun 20\1", text)
    text = re.sub(r"\b0?7\.?(\d{2})\b", r"Jul 20\1", text)
    text = re.sub(r"\b0?8\.?(\d{2})\b", r"Aug 20\1", text)
    text = re.sub(r"\b0?9\.?(\d{2})\b", r"Sep 20\1", text)
    text = re.sub(r"\b10\.?(\d{2})\b", r"Oct 20\1", text)
    text = re.sub(r"\b11\.?(\d{2})\b", r"Nov 20\1", text)
    text = re.sub(r"\b12\.?(\d{2})\b", r"Dec 20\1", text)
    text = re.sub(r"([A-Za-z]{3} 20\d{2})\s*[–-]\s*$", r"\1 – Present", text)
    return text

# ============================================================
# 2️⃣ Новые функции для совместимости с main.py (не ломают старый код)
# ============================================================

def extract_structure_with_gpt(text: str) -> dict:
    """Извлекает базовую структуру (скелет) CV."""
    return ask_chatgpt(text, mode="structure")


def extract_details_with_gpt(text: str, structure: dict) -> dict:
    """
    Заполняет детальную информацию в структуру CV.
    Всегда требует заполнения полей duration с точными диапазонами дат.
    """
    merged_prompt = {
        "instruction": (
            "Extract ALL project details from the CV, including exact durations "
            "(start and end dates, or 'Present'). If dates are not explicitly written, "
            "infer them logically from the context or timeline order."
        ),
        "structure": structure,
        "text": text
    }
    return ask_chatgpt(merged_prompt, mode="details")



def auto_fix_missing_fields(data: dict) -> dict:
    """Автоматически заполняет пустые поля в JSON."""
    return ask_chatgpt(data, mode="fix")

if __name__ == "__main__":
    # Тестовый запуск
    text = "Lead BI Developer, Azure Databricks, 07.21 – Jetzt"
    print(json.dumps(ask_chatgpt(text, mode="structure"), indent=2, ensure_ascii=False))
