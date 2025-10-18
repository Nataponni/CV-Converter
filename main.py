import os
import re
import time

from pdf_processor import prepare_cv_text
from chatgpt_client import (
    extract_structure_with_gpt,
    extract_details_with_gpt,
    auto_fix_missing_fields,
)
from skill_mapper import remap_hard_skills
from postprocess import unify_languages, unify_durations, clean_duplicates_in_skills
from utils import save_json, has_empty_fields
from schema import validate_schema


# Пути к файлам
INPUT_PDF = "data_input/CV_Kunde_1.pdf"
OUTPUT_JSON = "data_output/result_1.json"


# ============================================================
# 🔹 Вспомогательные функции
# ============================================================
def filter_explicit_domains(text: str, domains: list[str]) -> list[str]:
    """
    Расширяет поиск доменов по ключевым словам и контексту.
    """
    domain_keywords = {
        "Machine Learning": ["machine learning", "ml", "deep learning", "neural network"],
        "AI": ["artificial intelligence", "ai model", "generative ai"],
        "Data Engineering": ["data pipeline", "data ingestion", "etl", "databricks", "snowflake"],
        "MLOps": ["mlops", "model deployment", "ci/cd for models", "vertex ai", "sagemaker"],
        "Cloud": ["aws", "azure", "gcp", "kubernetes", "terraform"],
        "Analytics": ["bi", "power bi", "analytics", "dashboards", "reporting"],
        "IoT": ["iot", "connected devices", "sensor data", "predictive maintenance"],
        "Finance": ["banking", "fintech", "risk model", "insurance"],
        "Healthcare": ["medical", "health", "pharma", "clinical"],
        "Manufacturing": ["factory", "industrial", "process optimization", "production"],
    }

    found = set()
    text_l = text.lower()
    for domain, keywords in domain_keywords.items():
        if any(k in text_l for k in keywords):
            found.add(domain)

    # Сохраняем только домены, которые GPT тоже вернул (если есть)
    if domains:
        found.update(domains)

    return sorted(found)


def shorten_profile_summary(text: str, max_chars: int = 1200) -> str:
    """
    Обрезает длинное описание профиля, если GPT выдал слишком длинный текст.
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())
    if len(text) > max_chars:
        cut = text[:max_chars]
        if "." in cut:
            cut = cut[:cut.rfind(".") + 1]
        return cut.strip()
    return text.strip()


# ============================================================
# 🔹 Главный пайплайн
# ============================================================

def main():
    start_time = time.time()
    print("🚀 Starting CV Extraction & Structuring Pipeline v2.0")

    # 1️⃣ Подготовка текста из PDF
    prepared_text = prepare_cv_text(INPUT_PDF)

    # 2️⃣ GPT Шаг 1 — Извлечение структуры
    print("\n🧩 Step 1: Extracting CV structure...")
    structure = extract_structure_with_gpt(prepared_text)

    # 3️⃣ GPT Шаг 2 — Детализация и заполнение данных
    print("\n🔍 Step 2: Extracting detailed content...")
    result = extract_details_with_gpt(prepared_text, structure)

    # 4️⃣ Автозаполнение пропусков
    print("\n🤖 Step 3: Auto-filling missing fields...")
    if has_empty_fields(result):
        result = auto_fix_missing_fields(result)

    # 5️⃣ Проверка и валидация JSON
    print("\n📏 Step 4: Schema validation...")
    result = validate_schema(result)

    # 6️⃣ Постобработка данных
    print("\n🧼 Step 5: Normalizing and cleaning data...")
    result["hard_skills"] = remap_hard_skills(result.get("hard_skills", {}))
    result["hard_skills"] = clean_duplicates_in_skills(result["hard_skills"])
    result["languages"] = unify_languages(result.get("languages", []), original_text=prepared_text)

    # 7️⃣ Применение фильтров и сокращение профиля
    explicit_domains = filter_explicit_domains(prepared_text, result.get("domains", []))
    if explicit_domains:
        result["domains"] = explicit_domains
    result["profile_summary"] = shorten_profile_summary(result.get("profile_summary", ""))

    # 8️⃣ Сохранение JSON результата
    save_json(OUTPUT_JSON, result)

    elapsed = time.time() - start_time
    print(f"\n✅ Process completed successfully in {elapsed:.2f}s")
    print(f"💾 Result saved to: {OUTPUT_JSON}")


# ============================================================
# 🔹 Точка входа
# ============================================================

if __name__ == "__main__":
    main()
