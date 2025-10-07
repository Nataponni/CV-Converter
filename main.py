import os
import re
import time

from pdf_processor import extract_text_by_page, clean_text
from chatgpt_client import ask_chatgpt
from utils import save_json, has_empty_fields
from fill_cv import fill_missing_fields
from skill_mapper import remap_hard_skills

INPUT_PDF = "data_input/CV_Kunde_2.pdf"
OUTPUT_JSON = "data_output/result_2.json"


def filter_explicit_domains(text: str, domains: list[str]) -> list[str]:
    """
    Sucht explizit erwähnte 'Domains' im Text (z. B. FinTech, AI, Healthcare).
    Gibt nur diejenigen zurück, die tatsächlich im Text vorkommen.
    """
    match = re.search(r"(Domains\s*[:\-]?\s*)([\s\S]{0,500})", text, re.IGNORECASE)
    if not match:
        return []

    block = match.group(2)
    return [d for d in domains if re.search(rf"\b{re.escape(d)}\b", block, re.IGNORECASE)]


def shorten_profile_summary(text: str, max_chars: int = 600) -> str:
    """
    Kürzt die Profilbeschreibung (profile_summary) auf eine maximale Länge
    und entfernt überflüssige Leerzeichen.
    """
    if not text:
        return ""
    # Doppelte Leerzeichen entfernen
    text = re.sub(r'\s+', ' ', text.strip())
    if len(text) > max_chars:
        # Wenn zu lang, bis zum letzten Satzende kürzen
        shortened = text[:max_chars]
        if "." in shortened:
            shortened = shortened[:shortened.rfind(".") + 1]
        return shortened.strip()
    return text.strip()


def main():
    """
    Hauptfunktion:
    1. Extrahiert Text aus einer PDF-Datei.
    2. Übergibt den gesamten Text an ChatGPT zur Analyse.
    3. Normalisiert den Bereich 'hard_skills'.
    4. Filtert Domains, falls sie explizit im Text genannt sind.
    5. Kürzt die Profilbeschreibung.
    6. Füllt fehlende Felder (optional) und speichert das Ergebnis als JSON.
    """
    start = time.time()

    # 1️⃣ Text aus PDF extrahieren und bereinigen
    pages = extract_text_by_page(INPUT_PDF)
    full_text = "\n".join(clean_text(p) for p in pages)

    # 2️⃣ Analyse durch ChatGPT
    result = ask_chatgpt(full_text)

    # 3️⃣ Hard Skills an vereinheitlichte Struktur anpassen
    result["hard_skills"] = remap_hard_skills(result.get("hard_skills", {}))

    # 4️⃣ Explizit erwähnte Domains erkennen
    explicit_domains = filter_explicit_domains(full_text, result.get("domains", []))

    if explicit_domains:
        # Wenn Domains explizit genannt sind – nur diese übernehmen
        result["domains"] = explicit_domains
    else:
        # Sonst bestehende Domain-Liste beibehalten
        result["domains"] = result.get("domains", [])

    # 5️⃣ Profiltext kürzen und bereinigen
    result["profile_summary"] = shorten_profile_summary(result.get("profile_summary", ""))

    # 6️⃣ Fehlende Felder auffüllen, falls vorhanden
    if has_empty_fields(result):
        result = fill_missing_fields(result)

    # 7️⃣ Ergebnis als JSON-Datei speichern
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    save_json(OUTPUT_JSON, result)

    print(f"\n✅ Finale JSON-Datei gespeichert unter: {OUTPUT_JSON}")
    print(f"⏱️ Verarbeitungszeit: {time.time() - start:.2f} Sekunden")


if __name__ == "__main__":
    main()
