import streamlit as st
import json, os, tempfile, time
import threading
from pdf_processor import prepare_cv_text
from chatgpt_client import ask_chatgpt
from postprocess import postprocess_filled_cv
from cv_pdf_generator import create_pretty_first_section

# --- Seiteneinstellungen ---
st.set_page_config(page_title="CV-Konverter", page_icon="📄")
st.title("📄 CV-Konverter")

# 1️⃣ Datei-Upload
uploaded_file = st.file_uploader("Wähle eine PDF-Datei aus", type=["pdf"])

def is_new_candidate(uploaded_file):
    if not uploaded_file:
        return False
    last_file = st.session_state.get("last_uploaded_file_name", None)
    return uploaded_file.name != last_file

def clear_candidate_data():
    keys_to_clear = [
        "filled_json", "json_bytes", "pdf_bytes", "pdf_name",
        "raw_text", "pdf_path", "projects_experience",
        "profile_summary", "v3_summary_text", "v3_summary_area"
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)

if uploaded_file:
    # Очистка всех данных, если загружен новый кандидат
    if is_new_candidate(uploaded_file):
        clear_candidate_data()
        st.session_state["last_uploaded_file_name"] = uploaded_file.name

    # Сохраняем PDF во временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        pdf_path = tmp.name
    st.success(f"✅ Datei hochgeladen: {uploaded_file.name}")

        # --- Session-State Initialisierung (обязательно) ---
    st.session_state.setdefault("selected_model", "gpt-4o-mini")

    # --- Modell-Auswahl ---
    MODEL_OPTIONS = {
        "Schnell (geringere Qualität)": "gpt-4o-mini",
        "Langsamer (Genauer)": "gpt-5-mini"
    }

    st.radio(
        "Modell auswählen",
        options=list(MODEL_OPTIONS.keys()),
        key="model_label"
    )

    st.session_state["selected_model"] = MODEL_OPTIONS[st.session_state["model_label"]]

    # 2️⃣ Konvertierung starten
    if st.button("🚀 Konvertierung starten"):
        # Sichtbare, persistente Status-Komponenten
        progress_box = st.container()
        with progress_box:
            progress = st.progress(1)
        progress_value = 1
        status_text = st.empty()
        time_info = st.empty()
        start_time = time.time()

        try:
            # --- Schritt 1: Text extrahieren ---
            status_text.text("📖 Text wird extrahiert…")
            prepared_text, raw_text = prepare_cv_text(pdf_path)
            st.session_state["raw_text"] = raw_text
            st.session_state["pdf_path"] = pdf_path  # (для восстановления при повторном использовании)

            for i in range(1, 26, 2):
                time.sleep(0.1)
                progress.progress(i)
                progress_value = i
                time_info.text(f"⏱ {round(time.time() - start_time, 1)} Sekunden vergangen")

            # --- Schritt 2: Anfrage an ChatGPT ---
            status_text.text("🤖 Anfrage wird an ChatGPT gesendet…")
            holder = {"value": None, "error": None}
            # 👇 ВАЖНО: копируем значение ДО thread
            selected_model = st.session_state["selected_model"]

            def _run_gpt():
                holder["value"] = ask_chatgpt(
                    prepared_text,
                    mode="details",
                    model=selected_model  # ✅ безопасно
                )

            t = threading.Thread(target=_run_gpt, daemon=True)
            t.start()

            anim_start = time.time()
            # animate progress between 5..95 while waiting
            with st.spinner("Modell arbeitet…"):
                while t.is_alive():
                    elapsed = time.time() - start_time
                    # Monotones Fortschreiten bis max. 95%
                    progress_value = min(progress_value + 1, 95)
                    progress.progress(progress_value)
                    time_info.text(f"⏱ {round(elapsed, 1)} Sekunden vergangen")
                    time.sleep(0.15)

            if holder.get("error"):
                raise holder["error"]
            result = holder.get("value")

            # --- Schritt 3: JSON verarbeiten ---
            if "raw_response" in result and result["raw_response"]:
                status_text.text("🧩 Daten werden verarbeitet…")
                filled_json = json.loads(result["raw_response"])
                filled_json = postprocess_filled_cv(filled_json, raw_text)

                for i in range(56, 76, 2):
                    time.sleep(0.15)
                    progress.progress(i)
                    progress_value = i
                    time_info.text(f"⏱ {round(time.time() - start_time, 1)} Sekunden vergangen")

                # --- Schritt 4: PDF generieren (einmalig) ---
                status_text.text("📝 PDF wird erstellt…")
                output_dir = "data_output"
                os.makedirs(output_dir, exist_ok=True)

                # Нормализация должности в ключ 'title'
                if not filled_json.get("title"):
                    filled_json["title"] = (
                        filled_json.get("position")
                        or filled_json.get("role")
                        or ""
                    )

                for i in range(76, 96, 2):
                    time.sleep(0.05)
                    progress.progress(i)
                    progress_value = i
                    time_info.text(f"⏱ {round(time.time() - start_time, 1)} Sekunden vergangen")

                # --- Automatische Benennung des Dokuments ---
                full_name = filled_json.get("full_name", "").strip()
                position = (
                    filled_json.get("title")
                    or filled_json.get("position")
                    or filled_json.get("role")
                    or ""
                ).strip()

                first_name = full_name.split(" ")[0].title() if full_name else "Unbekannt"
                position = position.title() if position else "Unbekannte Position"
                pdf_name = f"CV Inpro {first_name} {position}"

                # --- PDF generieren mit richtigem Namen ---
                output_dir = "data_output"
                os.makedirs(output_dir, exist_ok=True)
                pdf_path = create_pretty_first_section(
                    filled_json, output_dir=output_dir, prefix=pdf_name
                )

                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                # 💾 Ergebnisse speichern
                st.session_state["filled_json"] = filled_json
                st.session_state["json_bytes"] = json.dumps(
                    filled_json, indent=2, ensure_ascii=False
                ).encode("utf-8")
                st.session_state["pdf_bytes"] = pdf_bytes
                st.session_state["pdf_name"] = pdf_name


            else:
                st.error("⚠️ Das Modell hat keine Daten zurückgegeben.")

        except Exception as e:
            st.error(f"❌ Fehler bei der Verarbeitung: {e}")

# 3️⃣ Downloadbereich
if "filled_json" in st.session_state:
    st.markdown("---")
    st.subheader("🛠 Manuelle Bearbeitung")

    # Создаем редактируемую копию
    edited = dict(st.session_state["filled_json"]) if isinstance(st.session_state["filled_json"], dict) else {}
    # Нормализация ключа languages, чтобы редактор всегда отображался
    if not isinstance(edited.get("languages"), list):
        if isinstance(edited.get("languages"), str) and edited["languages"].strip():
            edited["languages"] = []  # можно попытаться разобрать, но лучше явно пустой список
        else:
            edited["languages"] = []

    # Основные поля
    col_a, col_b = st.columns(2)
    with col_a:
        if "full_name" in edited:
            edited["full_name"] = st.text_input("Vollständiger Name", value=str(edited.get("full_name", "")), key="full_name")
        if "first_name" in edited:
            edited["first_name"] = st.text_input("Vorname", value=str(edited.get("first_name", "")), key="first_name")
    with col_b:
        # Единый ключ: title
        if "title" in edited or any(k in edited for k in ["position", "role"]):
            current_title = str(edited.get("title") or edited.get("position") or edited.get("role") or "")
            edited["title"] = st.text_input("Position (title)", value=current_title, key="title")

    # Контакты (dict)
    if isinstance(edited.get("contacts"), dict):
        with st.expander("Kontakte", expanded=False):
            contacts = dict(edited.get("contacts", {}))
            for k, v in contacts.items():
                contacts[k] = st.text_input(f"{k}", value=str(v), key=f"contacts_{k}")
            edited["contacts"] = contacts

    # Короткое описание / Summary
    if "profile_summary" in edited:
        edited["profile_summary"] = st.text_area("Kurzbeschreibung (profile_summary)", value=str(edited.get("profile_summary", "")), height=140, key="profile_summary")
    else:
        for summary_key in ["summary", "about", "profile"]:
            if summary_key in edited:
                edited[summary_key] = st.text_area("Kurzbeschreibung", value=str(edited.get(summary_key, "")), height=140, key=f"{summary_key}")
                break

    # Опыт / Проекты (list[dict]) — основной ключ: projects_experience
    if isinstance(edited.get("projects_experience"), list):
        with st.expander("Projekte / Erfahrung (projects_experience)", expanded=True):
            # Подсказка структуры
            st.caption("Struktur: { project_title, overview, role, duration, responsibilities[], tech_stack[] }")
            # Табличный редактор с возможностью добавлять/удалять строки
            edited["projects_experience"] = st.data_editor(
                edited["projects_experience"],
                num_rows="dynamic",
                use_container_width=True,
                key="ed_projects_experience"
            )

            # Удаление дублей (по паре project_title+duration)
            def _dedupe_projects(items: list[dict]) -> list[dict]:
                seen = set()
                result = []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    key = (str(it.get("project_title", "")).strip().lower(), str(it.get("duration", "")).strip().lower())
                    if key not in seen:
                        seen.add(key)
                        result.append(it)
                return result
            if st.button("🧹 Doppelte Projekte entfernen", key="btn_dedupe_projects"):
                edited["projects_experience"] = _dedupe_projects(edited.get("projects_experience", []))
                st.success("Duplikate entfernt")
    else:
        # Альтернативные ключи, если структура иная
        for exp_key in ["experience", "work_experience", "jobs"]:
            if isinstance(edited.get(exp_key), list):
                with st.expander("Berufserfahrung", expanded=False):
                    edited[exp_key] = st.data_editor(
                        edited[exp_key],
                        num_rows="dynamic",
                        use_container_width=True,
                        key=f"ed_{exp_key}"
                    )
                break

    # Образование: поддержка строкового поля или списка объектов
    if isinstance(edited.get("education"), list):
        with st.expander("Ausbildung (education)", expanded=False):
            edited["education"] = st.data_editor(
                edited["education"],
                num_rows="dynamic",
                use_container_width=True,
                key="ed_education"
            )
    elif isinstance(edited.get("education"), str):
        edited["education"] = st.text_area("Ausbildung (education)", value=edited.get("education", ""), height=120, key="education_text")

    # Навыки (list[str])
    if isinstance(edited.get("skills"), list):
        skills_text = ", ".join(map(str, edited.get("skills", [])))
        skills_text = st.text_area("Fähigkeiten (durch Komma getrennt)", value=skills_text, height=80, key="skills_text")
        edited["skills"] = [s.strip() for s in skills_text.split(",") if s.strip()]

    # Языки (list[dict]) — поддержка пустого списка через шаблон строки
    if isinstance(edited.get("languages"), list):
        with st.expander("Sprachen (languages)", expanded=False):
            lang_rows = edited.get("languages", [])
            template_row = {"language": "", "level": ""}
            if not lang_rows:
                lang_rows = [template_row]
            # column_config, чтобы появились столбцы даже при пустых/шаблонных данных
            lang_rows = st.data_editor(
                lang_rows,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "language": st.column_config.TextColumn("Sprache"),
                    "level": st.column_config.TextColumn("Niveau")
                },
                key="ed_languages"
            )
            # очищаем полностью пустые строки
            cleaned_langs = []
            for r in lang_rows:
                if isinstance(r, dict):
                    lang = str(r.get("language", "")).strip()
                    lvl = str(r.get("level", "")).strip()
                    if lang or lvl:
                        cleaned_langs.append({"language": lang, "level": lvl})
            edited["languages"] = cleaned_langs

    # Домены (list[str])
    if isinstance(edited.get("domains"), list):
        domains_text = ", ".join(map(str, edited.get("domains", [])))
        domains_text = st.text_area("Domänen (durch Komma getrennt)", value=domains_text, height=80, key="domains_text")
        edited["domains"] = [s.strip() for s in domains_text.split(",") if s.strip()]

    # Hard skills (dict[str, list[str]])
    if isinstance(edited.get("hard_skills"), dict):
        with st.expander("Hard Skills (nach Kategorien)", expanded=False):
            hs = dict(edited.get("hard_skills", {}))
            for cat, tools in hs.items():
                tools_list = []
                if isinstance(tools, list):
                    tools_list = [str(t) for t in tools]
                elif isinstance(tools, str):
                    tools_list = [t.strip() for t in tools.split(",") if t.strip()]
                tools_text = ", ".join(tools_list)
                new_text = st.text_area(f"{cat}", value=tools_text, height=60, key=f"hs_{cat}")
                hs[cat] = [t.strip() for t in new_text.split(",") if t.strip()]
            edited["hard_skills"] = hs

    # Skills overview (list[dict])
    if isinstance(edited.get("skills_overview"), list):
        with st.expander("Skills-Übersicht", expanded=False):
            rows = edited.get("skills_overview", [])
            # шаблон строки, чтобы редактор был редактируемым даже при пустом списке
            if not rows:
                rows = [{"category": "", "tools": [], "years_of_experience": ""}]
            edited["skills_overview"] = st.data_editor(
                rows,
                num_rows="dynamic",
                use_container_width=True,
                key="ed_skills_overview"
            )

    # --- V3 Text Summary (optional) ---
    # Получаем данные, которые были сохранены после успешной конвертации
    cv_data_for_summary = st.session_state.get("filled_json", {}) # Используйте 'filled_json' или тот ключ, где лежат финальные данные
    st.markdown("### 📝 Textbasierte Zusammenfassung")
    if st.button("Zusammenfassung generieren", key="btn_generate_v3_summary"):
        with st.spinner("GPT generiert die textbasierte Zusammenfassung…"):
            from chatgpt_client import gpt_generate_text_cv_summary
            try:
                summary_result = gpt_generate_text_cv_summary(
                    cv_data=cv_data_for_summary,
                    model="gpt-4o-mini"
                )
                if summary_result.get("success") and summary_result.get("output_text"):
                    st.session_state["v3_summary_text"] = summary_result["output_text"]
                    st.success("Summary erfolgreich erstellt.")
                else:
                    st.warning("⚠️ Keine Zusammenfassung erhalten.")
            except Exception as e:
                st.error(f"Fehler bei der Generierung: {e}")

    if "v3_summary_text" in st.session_state:
        st.text_area(
            "📄 Zusammenfassung (nur Text)",
            value=st.session_state["v3_summary_text"],
            height=300,
            disabled=False,
            key="v3_summary_area"
        )

    # Резервный редактор всего JSON (на случай редких полей)
    with st.expander("Erweiterter JSON-Editor", expanded=False):
        raw_json_text = st.text_area(
            "JSON (vollständig)",
            value=json.dumps(edited, ensure_ascii=False, indent=2),
            height=240,
            key="raw_json_editor"
        )
        if st.button("Änderungen aus JSON übernehmen", key="apply_raw_json"):
            try:
                edited = json.loads(raw_json_text)
                st.success("JSON übernommen")
            except Exception as e:
                st.error(f"JSON-Parsing-Fehler: {e}")

    # Кнопки управления
    if st.button("💾 Änderungen speichern & PDF erzeugen", key="save_and_regen"):
        # 1) логика сохранения JSON (как в save_changes)
        if not edited.get("title"):
            edited["title"] = edited.get("position") or edited.get("role") or ""
        if isinstance(edited.get("languages"), list):
            edited["languages"] = [
                r for r in edited["languages"]
                if isinstance(r, dict)
                and (str(r.get("language", "")).strip() or str(r.get("level", "")).strip())
            ]
        st.session_state["filled_json"] = edited
        st.session_state["json_bytes"] = json.dumps(
            edited, indent=2, ensure_ascii=False
        ).encode("utf-8")

        # 2) логика генерации PDF (как в regen_pdf)
        full_name = edited.get("full_name", "").strip()
        position = (
            edited.get("title")
            or edited.get("position")
            or edited.get("role")
            or ""
        ).strip()
        first_name = full_name.split(" ")[0].title() if full_name else "Unbekannt"
        position_t = position.title() if position else "Unbekannte Position"
        pdf_name_new = f"CV Inpro {first_name} {position_t}"

        output_dir = "data_output"
        os.makedirs(output_dir, exist_ok=True)
        pdf_path_new = create_pretty_first_section(
            edited, output_dir=output_dir, prefix=pdf_name_new
        )
        with open(pdf_path_new, "rb") as f:
            st.session_state["pdf_bytes"] = f.read()
        st.session_state["pdf_name"] = pdf_name_new

        st.success("Änderungen gespeichert und PDF aktualisiert")

    st.markdown("---")
    st.subheader("⬇️ Ergebnisse herunterladen")

    pdf_name = st.session_state.get("pdf_name", "CV_Streamlit")

    st.download_button(
        label="📘 JSON herunterladen",
        data=st.session_state["json_bytes"],
        file_name=f"{pdf_name}_result.json",
        mime="application/json",
        key="download_json"
    )

    if "pdf_bytes" in st.session_state:
        st.download_button(
            label="📄 PDF herunterladen",
            data=st.session_state["pdf_bytes"],
            file_name=f"{pdf_name}.pdf",
            mime="application/pdf",
            key="download_pdf"
        )
