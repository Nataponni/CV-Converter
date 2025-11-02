import os
import json
import time
import logging
from multiprocessing import Process, Queue
from pdf_processor import prepare_cv_text
from postprocess import postprocess_filled_cv
from chatgpt_client import ask_chatgpt

# === Пути ===
INPUT_PDF = "data_input/CV Manuel Wolfsgruber.pdf"
RAW_GPT_JSON = "data_output/raw_gpt.json"
OUTPUT_JSON = "data_output/result_Manuel_1.json"

# --- вынесенная функция ---
def gpt_worker(q, mode, text, base_structure):
    """Выполняет изолированный вызов GPT в отдельном процессе."""
    from chatgpt_client import ask_chatgpt
    result = ask_chatgpt(text, mode=mode, base_structure=base_structure)
    q.put(result)


def ask_chatgpt_isolated(mode, text, base_structure=None):
    q = Queue()
    p = Process(target=gpt_worker, args=(q, mode, text, base_structure))
    p.start()
    p.join()

    if not q.empty():
        return q.get()
    else:
        logging.warning("⚠️ No data returned from GPT subprocess.")
        return {"raw_response": "", "error": "No data returned from subprocess"}

# === Основной пайплайн ===
def main():
    start_time = time.time()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info("🚀 Starting full CV pipeline (PDF → GPT → JSON)...")

    # 1️⃣ Подготовка текста
    prepared_text, raw_text = prepare_cv_text(INPUT_PDF)
    logging.info("📄 Text successfully extracted and normalized.")

# 2️⃣ STRUCTURE
    logging.info("📨 Requesting structure from GPT...")
    structure_raw = ask_chatgpt(prepared_text, mode="structure")

    if not structure_raw or "raw_response" not in structure_raw:
        logging.error("❌ Failed to get structure from GPT.")
        return

    try:
        base_structure = json.loads(structure_raw["raw_response"])
    except Exception as e:
        logging.error(f"⚠️ Structure parsing failed: {e}")
        base_structure = None

    # 3️⃣ DETAILS
    logging.info("📨 Requesting detailed CV data from GPT...")
    result = ask_chatgpt(prepared_text, mode="details", base_structure=base_structure)


    if not result or "raw_response" not in result:
        logging.error("❌ GPT did not return a valid response.")
        return

    # 4️⃣ Сохраняем "сырой" JSON
    try:
        filled_json = json.loads(result["raw_response"])
        os.makedirs(os.path.dirname(RAW_GPT_JSON), exist_ok=True)
        with open(RAW_GPT_JSON, "w", encoding="utf-8") as f:
            json.dump(filled_json, f, indent=2, ensure_ascii=False)
        logging.info(f"💾 Raw GPT output saved to: {RAW_GPT_JSON}")
    except json.JSONDecodeError as e:
        logging.error("❌ Invalid JSON from GPT:")
        logging.error(e)
        return

    # 5️⃣ Постобработка
    logging.info("🧩 Running postprocessing...")
    filled_json = postprocess_filled_cv(filled_json, raw_text)

    # 6️⃣ Метаданные
    filled_json["_meta"] = {
        "source_pdf": INPUT_PDF,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "processing_time_sec": round(time.time() - start_time, 2),
        "model": "gpt-5-mini",
    }

    # 7️⃣ Сохраняем финал
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(filled_json, f, indent=2, ensure_ascii=False)

    logging.info(f"✅ Final result saved to: {OUTPUT_JSON}")
    logging.info(f"📊 Projects: {len(filled_json.get('projects_experience', []))}")
    logging.info(f"🗣 Languages: {len(filled_json.get('languages', []))}")
    logging.info(f"⏱ Duration: {round(time.time() - start_time, 2)} sec")


if __name__ == "__main__":
    main()
