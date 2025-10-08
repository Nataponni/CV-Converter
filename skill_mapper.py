import re
from tech_mapping import TECH_MAPPING

def remap_hard_skills(hard_skills_from_gpt):
    """
    Vereinheitlicht die Struktur von 'hard_skills':
    - Beibehaltung von 'name' und 'years_experience' aus der GPT-Ausgabe
    - Ordnet Tools anhand von TECH_MAPPING Kategorien zu
    - Entfernt Duplikate und bereinigt leere Einträge
    """
    mapped_skills = {
        "cloud_platforms": [],
        "devops_iac": [],
        "ci_cd_tools": [],
        "containers_orchestration": [],
        "programming_languages": [],
        "databases": [],
        "backend": [],
        "frontend": [],
        "data_engineering": [],
        "etl_tools": [],
        "analytics_bi": [],
        "testing_tools": [],
        "monitoring_security": [],
        "version_control": [],
        "ai_ml_tools": [],
        "security": [],
        "infrastructure": [],
        "other_tools": []
    }


    # Jedes Tool prüfen und zuordnen
    for category, tools in hard_skills_from_gpt.items():
        for item in tools:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                years = item.get("years_experience", 0)
            else:
                name = str(item).strip()
                years = 0

            if not name:
                continue

            # Kategorie durch TECH_MAPPING prüfen
            matched = False
            for pattern, mapped_category in TECH_MAPPING.items():
                if re.search(pattern, name.lower()):
                    mapped_skills[mapped_category].append({
                        "name": name,
                        "years_experience": years
                    })
                    matched = True
                    break

            if not matched:
                mapped_skills["other_tools"].append({
                    "name": name,
                    "years_experience": years
                })

    # Duplikate entfernen
    for cat in mapped_skills:
        unique = []
        seen = set()
        for t in mapped_skills[cat]:
            key = t["name"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(t)
        mapped_skills[cat] = unique

    return mapped_skills

if __name__ == "__main__":
    import json
    # Testmodus: vorhandene JSON-Datei einlesen
    with open("data_output/result_2.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    original_skills = data.get("hard_skills", {})
    remapped = remap_hard_skills(original_skills)

    import pprint
    # Ausgabe der neu zugeordneten Hard Skills
    pprint.pprint(remapped, sort_dicts=False)
