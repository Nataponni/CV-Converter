import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_chatgpt(text):
    prompt = f"""
TASK: Extract structured data from the input text (CV, PDF text) and return ONLY JSON according to the schema.

INSTRUCTIONS:
- In "projects_experience":
  * Always extract "duration" — include any dates, years, or ranges (e.g. "Jan 2022 – May 2024", "2021–Present").
    Never leave it empty.
  * Extract "responsibilities" as short, factual bullet points (max 12 words each),
    preserving the action verbs from the text — no generic filler like "was responsible for", "helped to", etc.
  * Include up to 6–8 bullet points per project, prioritizing the most senior-level or technical tasks.
  * If multiple projects share time ranges or overlap, still repeat full durations.

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
    response = client.chat.completions.create(
        model="gpt-5-mini", 
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You must extract structured data and return only JSON. Follow the schema exactly."},
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content.strip()

    usage = response.usage
    print(f"Tokens: Input={usage.prompt_tokens}, Output={usage.completion_tokens}, Total={usage.total_tokens}")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"raw_response": content}


if __name__ == "__main__":
  pass