from pdf_processor import extract_text_from_pdf
from chatgpt_client import ask_chatgpt
from utils import save_json
import os

INPUT_PDF = "data_input/CV_Kunde_2.pdf"
OUTPUT_JSON = "data_output/result_2.json"

def main():
    # 1. PDF lesen
    text = extract_text_from_pdf(INPUT_PDF)

    if not text.strip():
        print("⚠️ PDF ist leer oder konnte nicht gelesen werden")
        return

    # 🔹 Sparmodus: Text kürzen (z. B. nur die ersten 1000 Zeichen)
    short_text = text[:1000]

    # 2. Anfrage an ChatGPT senden
    response_json = ask_chatgpt(short_text)

    # 3. Ergebnis speichern
    save_json(response_json, OUTPUT_JSON)

    print(f"\n✅ Fertig! Antwort gespeichert in {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
