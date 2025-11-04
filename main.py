import os
import json
import time
import logging
from pdf_processor import prepare_cv_text
from postprocess import postprocess_filled_cv, fix_open_date_ranges, safe_parse_if_str
from chatgpt_client import run_robust_cv_parsing
import ast

# === Pfade ===
INPUT_PDF = "data_input/CV Manuel Wolfsgruber.pdf"
RAW_GPT_JSON = "data_output/raw_gpt.json"
OUTPUT_JSON = "data_output/result_Manuel_1.json"

# === Hauptpipeline ===
def main():
    start_time = time.time()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info("🚀 Starte vollständige CV-Pipeline (PDF → GPT → JSON)...")

    # 1️⃣ Textvorbereitung (включая объединение блоков)
    prepared_text, raw_text = prepare_cv_text(INPUT_PDF)
    logging.info("📄 Text erfolgreich extrahiert und normalisiert (inkl. Projektdaten & Datumszeilen).")

    # 2️⃣ Anfrage an GPT mit Fallback-Logik
    logging.info("🧠 Starte robuste GPT-Analyse...")
    result = run_robust_cv_parsing(prepared_text)

    if not result.get("success"):
        logging.error("❌ GPT hat keine gültige Antwort geliefert.")
        return

    # 3️⃣ Rohdaten extrahieren
    filled_json = result.get("json", {})
    raw_gpt_response = result.get("raw_response", "")

    # 4️⃣ Passenden raw_text wählen
    raw_for_postprocess = raw_text
    if result.get("mode") == "direct-json":
        raw_for_postprocess = json.dumps(filled_json, ensure_ascii=False, indent=2)

    # 5️⃣ Rohdaten speichern
    os.makedirs(os.path.dirname(RAW_GPT_JSON), exist_ok=True)
    with open(RAW_GPT_JSON, "w", encoding="utf-8") as f:
        json.dump(filled_json, f, indent=2, ensure_ascii=False)
    logging.info(f"💾 Rohdaten von GPT gespeichert unter: {RAW_GPT_JSON}")

    # 6️⃣ Универсальная стабилизация типов
    for key in ["projects_experience", "skills_overview", "languages"]:
        filled_json[key] = safe_parse_if_str(filled_json.get(key))
        # если все еще строка — пробуем через ast.literal_eval
        if isinstance(filled_json.get(key), str):
            try:
                filled_json[key] = ast.literal_eval(filled_json[key])
            except Exception:
                filled_json[key] = []

    # 7️⃣ Nachbearbeitung (постпроцессинг)
    logging.info("🧩 Führe Nachbearbeitung durch...")
    filled_json = postprocess_filled_cv(filled_json, raw_for_postprocess)

    # 🧠 Повторная стабилизация после постпроцессора
    for key in ["projects_experience", "skills_overview", "languages"]:
        filled_json[key] = safe_parse_if_str(filled_json.get(key))
        if isinstance(filled_json.get(key), str):
            try:
                filled_json[key] = ast.literal_eval(filled_json[key])
            except Exception:
                filled_json[key] = []

    # 8️⃣ Автозаполнение ролей и дат (если GPT пропустил)
    for project in filled_json.get("projects_experience", []):
        # --- Role recovery ---
        if not project.get("role"):
            title = project.get("project_title", "")
            if title:
                import re
                match = re.search(r"\b(Developer|Engineer|Architect|Consultant|Manager|Lead|Analyst|Director|Specialist)\b", title, re.I)
                if match:
                    project["role"] = match.group(1)
                else:
                    project["role"] = "Consultant"

        # --- Duration recovery ---
        if not project.get("duration"):
            overview = project.get("overview", "")
            import re
            date_match = re.search(r"(\d{1,2}\.\d{2})\s*[–-]\s*(Jetzt|Heute|Present|\d{1,2}\.\d{2})", title + " " + overview)
            if date_match:
                start, end = date_match.groups()
                project["duration"] = f"{start} – {end}"
            else:
                prev = next((p for p in filled_json.get("projects_experience", []) if p.get("duration")), None)
                project["duration"] = prev["duration"] if prev else "Unspecified"

    # 👇 Auf offene Datumsbereiche prüfen (z. B. „bis heute“)
    filled_json = fix_open_date_ranges(filled_json)

    # 9️⃣ Metadaten hinzufügen
    filled_json["_meta"] = {
        "source_pdf": INPUT_PDF,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processing_time_sec": round(time.time() - start_time, 2),
        "model": "gpt-5-mini",
        "gpt_mode": result.get("mode")
    }

    # 🔟 Finale Daten speichern
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(filled_json, f, indent=2, ensure_ascii=False)

    # ℹ️ Logging summary
    logging.info(f"✅ Endergebnis gespeichert unter: {OUTPUT_JSON}")
    logging.info(f"📊 Projekte: {len(filled_json.get('projects_experience', []))}")
    logging.info(f"🗣 Sprachen: {len(filled_json.get('languages', []))}")
    logging.info(f"⏱ Dauer: {round(time.time() - start_time, 2)} Sekunden")

if __name__ == "__main__":
    main()
