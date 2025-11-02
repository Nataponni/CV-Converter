import streamlit as st
import os
import json
import time
from pdf_processor import prepare_cv_text
from chatgpt_client import ask_chatgpt
from postprocess import postprocess_filled_cv


# === Ordner vorbereiten ===
INPUT_DIR = "data_input"
OUTPUT_DIR = "data_output"
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

PREPARED_PATH = os.path.join(OUTPUT_DIR, "prepared_text.txt")
RAW_GPT_JSON = os.path.join(OUTPUT_DIR, "raw_gpt.json")
FINAL_JSON = os.path.join(OUTPUT_DIR, "result_final.json")


# === Streamlit ===
st.set_page_config(page_title="CV_Converter", layout="centered")
st.title("📄 CV_Converter")

# === Datei-Upload ===
uploaded_pdf = st.file_uploader("PDF-Datei hochladen", type=["pdf"])

# === Schritt 1: PDF-Verarbeitung ===
if st.button("🧩 Schritt 1: PDF vorbereiten"):
    if uploaded_pdf:
        input_path = os.path.join(INPUT_DIR, uploaded_pdf.name)
        with open(input_path, "wb") as f:
            f.write(uploaded_pdf.read())

        st.info("Text wird aus PDF extrahiert und verarbeitet …")
        start = time.time()
        prepared_text, raw_text = prepare_cv_text(input_path)

        with open(PREPARED_PATH, "w", encoding="utf-8") as f:
            f.write(prepared_text)

        st.success(f"✅ Fertig! Datei gespeichert: {PREPARED_PATH}")
        st.caption(f"Dauer: {round(time.time()-start,1)} Sekunden")

        # === Download-Link für das Original-PDF ===
        with open(input_path, "rb") as pdf_file:
            st.download_button(
                label="📥 Ursprüngliche PDF-Datei herunterladen",
                data=pdf_file,
                file_name=uploaded_pdf.name,
                mime="application/pdf"
            )

    else:
        st.error("Bitte zuerst eine PDF-Datei hochladen.")


# === Schritt 2: GPT-Analyse ===
if st.button("🤖 Schritt 2: GPT-Analyse starten"):
    if not os.path.exists(PREPARED_PATH):
        st.error("Bitte zuerst Schritt 1 ausführen.")
    else:
        with open(PREPARED_PATH, "r", encoding="utf-8") as f:
            prepared_text = f.read()

        st.info("GPT wird ausgeführt … das kann einige Sekunden dauern.")
        start = time.time()

        structure_raw = ask_chatgpt(prepared_text, mode="structure")

        try:
            base_structure = json.loads(structure_raw["raw_response"])
        except Exception:
            base_structure = None

        result = ask_chatgpt(prepared_text, mode="details", base_structure=base_structure)

        if "raw_response" in result:
            try:
                filled_json = json.loads(result["raw_response"])

                with open(RAW_GPT_JSON, "w", encoding="utf-8") as f:
                    json.dump(filled_json, f, indent=2, ensure_ascii=False)

                st.info("Postprocessing läuft …")
                filled_json = postprocess_filled_cv(filled_json, prepared_text)

                filled_json["_meta"] = {
                    "source_pdf": uploaded_pdf.name,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "processing_time_sec": round(time.time() - start, 2),
                }

                with open(FINAL_JSON, "w", encoding="utf-8") as f:
                    json.dump(filled_json, f, indent=2, ensure_ascii=False)

                st.success("✅ Analyse abgeschlossen!")
                st.caption(f"Dauer: {round(time.time()-start,1)} Sekunden")
                st.json(filled_json)

                # === Download-Button für JSON-Ergebnis ===
                with open(FINAL_JSON, "rb") as json_file:
                    st.download_button(
                        label="📥 JSON-Ergebnis herunterladen",
                        data=json_file,
                        file_name="result_final.json",
                        mime="application/json"
                    )

            except json.JSONDecodeError:
                st.error("Ungültige JSON-Antwort von GPT:")
                st.text(result["raw_response"])
        else:
            st.error("GPT hat keine gültige Antwort geliefert.")

st.divider()
st.caption("© 2025 — CV_Converter")
