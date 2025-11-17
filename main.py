import os
import json
import time
import logging
from pdf_processor import prepare_cv_text
from postprocess import postprocess_filled_cv, fix_open_date_ranges, safe_parse_if_str
from chatgpt_client import (
    gpt_extract_cv_without_projects,
    gpt_extract_projects_text,
    gpt_structurize_projects_from_text,
)
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

    # 📁 Sicherstellen, dass der Output-Ordner existiert
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    # 🔹 Optional: подготовленный текст как отдельный артефакт (Schema-1-Text)
    schema1_text_path = os.path.join(os.path.dirname(OUTPUT_JSON), "schema1_text.txt")
    with open(schema1_text_path, "w", encoding="utf-8") as f:
        f.write(prepared_text)

    # 2️⃣ GPT: извлечение только проектного текста (TEXT 2)
    logging.info("🧠 GPT-Schritt 1b: Extrahiere reinen Projekttext...")
    projects_text_result = gpt_extract_projects_text(raw_text)
    if not projects_text_result.get("success"):
        logging.error("❌ GPT (Projekt-Text) hat keine gültige Antwort geliefert.")
        return

    projects_text = projects_text_result.get("text", "") or ""
    projects_raw_txt_path = os.path.join(os.path.dirname(OUTPUT_JSON), "projects_raw.txt")
    with open(projects_raw_txt_path, "w", encoding="utf-8") as f:
        f.write(projects_text)

    # 3️⃣ GPT-Schritt 2: CV ohne Projekte (Schema 1 aus TEXT 1)
    logging.info("🧠 GPT-Schritt 2: Extrahiere CV ohne Projekte...")
    base_result = gpt_extract_cv_without_projects(raw_text)
    if not base_result.get("success"):
        logging.error("❌ GPT (Schema ohne Projekte) hat keine gültige Antwort geliefert.")
        return
    base_cv = base_result.get("json", {}) or {}

    # 🔹 Сохраняем Schema 1 как JSON
    schema1_json_path = os.path.join(os.path.dirname(OUTPUT_JSON), "schema1.json")
    with open(schema1_json_path, "w", encoding="utf-8") as f:
        json.dump(base_cv, f, indent=2, ensure_ascii=False)

    # 4️⃣ GPT-Schritt 3: Структурирование проектов из TEXT 2 в целевую схему
    logging.info("🧠 GPT-Schritt 3: Strukturiere Projekte aus projects_raw.txt...")
    projects_struct_result = gpt_structurize_projects_from_text(projects_text)
    if not projects_struct_result.get("success"):
        logging.error("❌ GPT (Projekt-Structurierung) hat keine gültige Antwort geliefert.")
        return

    projects_payload = projects_struct_result.get("json", {}) or {}
    projects_experience = projects_payload.get("projects_experience", [])

    # 🔹 Сохраняем Schema 2 (только проекты) как JSON
    projects_schema_path = os.path.join(os.path.dirname(OUTPUT_JSON), "projects_schema.json")
    with open(projects_schema_path, "w", encoding="utf-8") as f:
        json.dump(projects_payload, f, indent=2, ensure_ascii=False)

    # 5️⃣ Merge: Schema 1 + Schema 2 (проекты)
    filled_json = base_cv
    filled_json["projects_experience"] = projects_experience
    raw_gpt_response = projects_struct_result.get("raw_response", "")

    # 4️⃣ Passenden raw_text wählen
    raw_for_postprocess = raw_text

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

    # 8️⃣ Автозаполнение ролей и дат перенесено в постпроцессинг.
    # Здесь намеренно НЕ подставляем роль по умолчанию (например, "Consultant")
    # и НЕ копируем duration из других проектов.
    # Все такие догадки теперь делает (или НЕ делает) только постпроцессор
    # на основе собственного текста каждого проекта.

    # 👇 Auf offene Datumsbereiche prüfen (z. B. „bis heute“)
    filled_json = fix_open_date_ranges(filled_json)

    # 9️⃣ Metadaten hinzufügen
    filled_json["_meta"] = {
        "source_pdf": INPUT_PDF,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processing_time_sec": round(time.time() - start_time, 2),
        "model": "gpt-5-mini",
        "gpt_mode": "two-step-projects"  # или любое фиксированное значение
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
