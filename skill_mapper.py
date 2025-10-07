import re
from tech_mapping import TECH_MAPPING

def remap_hard_skills(hard_skills_from_gpt):
    """
    Vereinheitlicht die Struktur von 'hard_skills':
    - Extrahiert alle Tool-Namen aus der Eingabe (z. B. [{"name": "...", "years_experience": ...}])
    - Ordnet sie den Kategorien aus TECH_MAPPING zu
    - Entfernt Duplikate und bereinigt leere Einträge
    """
    mapped_skills = {
        "cloud_platforms": [],
        "devops_iac": [],
        "monitoring_security": [],
        "programming_languages": [],
        "containers_orchestration": [],
        "ci_cd_tools": [],
        "databases": [],
        "backend": [],
        "frontend": [],
        "security": [],
        "ai_ml_tools": [],
        "other_tools": []
    }

    all_tools = set()

    # 1️⃣ Alle Tool-Namen aus den GPT-Ergebnissen sammeln
    for tools in hard_skills_from_gpt.values():
        for item in tools:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
            else:
                name = str(item).strip()
            if name:
                all_tools.add(name)

    # 2️⃣ Jedes Tool mithilfe von TECH_MAPPING einer Kategorie zuordnen
    for tool in all_tools:
        matched = False
        for pattern, category in TECH_MAPPING.items():
            if re.search(pattern, tool.lower()):
                mapped_skills[category].append(tool)
                matched = True
                break
        # Wenn kein Pattern übereinstimmt → unter "other_tools" speichern
        if not matched:
            mapped_skills["other_tools"].append(tool)

    # 3️⃣ Doppelte Einträge entfernen und alphabetisch sortieren
    for category in mapped_skills:
        mapped_skills[category] = sorted(list(set(mapped_skills[category])))

    return mapped_skills


if __name__ == "__main__":
    import json
    # Testmodus: vorhandene JSON-Datei einlesen
    with open("data_output/result_1.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    original_skills = data.get("hard_skills", {})
    remapped = remap_hard_skills(original_skills)

    import pprint
    # Ausgabe der neu zugeordneten Hard Skills
    pprint.pprint(remapped, sort_dicts=False)
