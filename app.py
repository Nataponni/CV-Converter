import streamlit as st
import json, os, tempfile
from pdf_processor import prepare_cv_text
from chatgpt_client import ask_chatgpt
from postprocess import postprocess_filled_cv
from cv_pdf_generator import create_pretty_first_section
import pandas as pd

# --- Seiteneinstellungen ---
st.set_page_config(page_title="CV-Konverter", page_icon="📄")
st.title("📄 CV-Konverter – Demo")

# 1️⃣ Datei-Upload
uploaded_file = st.file_uploader("Wähle eine PDF-Datei aus", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        pdf_path = tmp.name
    st.success(f"✅ Datei hochgeladen: {uploaded_file.name}")

    # 2️⃣ Konvertierung starten
    if st.button("🚀 Konvertierung starten"):
        st.info("📖 Text wird extrahiert…")
        prepared_text, raw_text = prepare_cv_text(pdf_path)

        st.info("🤖 Anfrage wird an ChatGPT gesendet…")
        result = ask_chatgpt(prepared_text, mode="details")

        if "raw_response" in result and result["raw_response"]:
            filled_json = json.loads(result["raw_response"])
            filled_json = postprocess_filled_cv(filled_json, raw_text)

            # 💾 In Session speichern
            st.session_state["filled_json"] = filled_json
            st.session_state["json_bytes"] = json.dumps(
                filled_json, indent=2, ensure_ascii=False
            ).encode("utf-8")

            st.success("✅ Konvertierung abgeschlossen!")
        else:
            st.error("⚠️ Das Modell hat keine Daten zurückgegeben.")

# 3️⃣ Downloadbereich
if "filled_json" in st.session_state:
    st.markdown("---")
    st.subheader("⬇️ Ergebnisse herunterladen")

    st.download_button(
        label="⬇️ JSON herunterladen",
        data=st.session_state["json_bytes"],
        file_name="cv_result.json",
        mime="application/json",
        key="download_json"
    )

    if st.button("📄 PDF-Bericht erstellen"):
        output_dir = "data_output"
        os.makedirs(output_dir, exist_ok=True)
        filled_json = st.session_state["filled_json"]
        pdf_path = create_pretty_first_section(
            filled_json, output_dir=output_dir, prefix="CV_Streamlit"
        )

        with open(pdf_path, "rb") as f:
            st.session_state["pdf_bytes"] = f.read()
        st.success("✅ PDF wurde erstellt!")

    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="⬇️ PDF-Bericht herunterladen",
            data=st.session_state["pdf_bytes"],
            file_name="cv_report.pdf",
            mime="application/pdf",
            key="download_pdf"
        )
