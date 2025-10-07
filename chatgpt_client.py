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
- Extract values only if they clearly appear or are strongly implied in the text (e.g. from education, work location, project descriptions).
- Do not invent data, but infer missing fields (like languages or domains) if there's strong context (e.g. English-language university → "English", cloud-related tools → "Cloud" domain).
- For lists (skills, tools, domains, languages), keep them:
  unique (no duplicates),
  relevant (clearly mentioned or strongly implied),
  consistently categorized (e.g., Terraform → devops_iac, Datadog → monitoring_security).
- Use the following fixed skill categories under `hard_skills`: cloud_platforms, devops_iac, monitoring_security, programming_languages, containers_orchestration, ci_cd_tools, ai_ml_tools, databases, backend, frontend, security, other_tools.
- If a value is missing or no confident match is found — return "" or [].
- Always return complete JSON with all schema fields, even if some are empty.
- Output must be valid JSON only — no extra text or formatting.

SCHEMA:
{{
  "full_name": "",
  "title": "",
  "education": "",
  "languages": [{{"language": "", "level": ""}}],
  "domains": [],
  "profile_summary": "",
"hard_skills": {{
  "cloud_platforms": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "devops_iac": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "monitoring_security": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "programming_languages": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "containers_orchestration": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "ci_cd_tools": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "ai_ml_tools": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "databases": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "backend": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "frontend": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "security": [
    {{ "name": "", "years_experience": 0 }}
  ],
  "other_tools": [
    {{ "name": "", "years_experience": 0 }}
  ]
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