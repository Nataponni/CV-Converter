import streamlit as st
import json, os, tempfile, time
import threading
import uuid
import hashlib
from pdf_processor import prepare_cv_text
from chatgpt_client import ask_chatgpt
from postprocess import postprocess_filled_cv, normalize_project_domains
from cv_pdf_generator import create_pretty_first_section

# --- Seiteneinstellungen ---
st.set_page_config(page_title="CV-Konverter", page_icon="📄")
st.title("📄 CV-Konverter")

# 1️⃣ Datei-Upload
uploaded_file = st.file_uploader("Wähle eine PDF-Datei aus", type=["pdf"])

def _stable_hash(obj) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        s = str(obj)
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _as_records(x):
    """Streamlit data_editor может вернуть list[dict] или DataFrame-like."""
    if x is None:
        return None
    if isinstance(x, list):
        return x
    if hasattr(x, "to_dict"):
        try:
            return x.to_dict(orient="records")
        except Exception:
            return None
    return None


def _norm_list(x):
    """Нормализует значения, которые должны быть list[str]."""
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v).strip() for v in x if str(v).strip()]
    if isinstance(x, str):
        # на случай если Streamlit/JSON превратил список в строку
        parts = [p.strip() for p in x.split(",")]
        return [p for p in parts if p]
    s = str(x).strip()
    return [s] if s else []


def _norm_domains(x):
    """Нормализуем домены и приводим к TitleCase."""
    return [d.strip().title() for d in _norm_list(x) if d and str(d).strip()]


def _domains_to_text(domains):
    """Список доменов -> строка через запятую для редактирования в таблице."""
    return ", ".join(_norm_list(domains))


def _domains_from_text(text):
    """Строка -> уникальный список доменов (title case)."""
    seen = set()
    out = []
    for d in _norm_domains(text):
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _load_domains_config() -> list[str]:
    """Загружает предустановленные домены из domains.json и нормализует их."""
    config_file = "domains.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Нормализуем в TitleCase, как остальные домены
                return sorted(set(d.strip().title() for d in data.get("domains", []) if d.strip()))
        except Exception as e:
            print(f"Ошибка при загрузке доменов: {e}")
    return []


def _save_domains_config(domains: list) -> bool:
    """Сохраняет обновленный список доменов в domains.json."""
    config_file = "domains.json"
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({"domains": sorted(set(domains))}, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка при сохранении доменов: {e}")
        return False


def _collect_project_domains_only(projects: list) -> list[str]:
    """Собирает ТОЛЬКО домены из проектов (без конфига)."""
    out = set()
    for p in projects or []:
        if isinstance(p, dict):
            for d in _norm_list(p.get("domains")):
                if d:
                    out.add(d)
    return sorted(out)


def _projects_to_display(projects: list) -> list:
    """Подготовка проектов для data_editor: оставляем domains как список, добавляем company."""
    display = []
    for p in projects or []:
        if isinstance(p, dict):
            row = dict(p)
            # Оставляем domains как список для отображения тегами
            row["domains"] = _norm_domains(row.get("domains", []))
            # Убеждаемся что company есть
            if "company" not in row:
                row["company"] = ""
            display.append(row)
        else:
            display.append(p)
    return display


def _projects_from_display(rows: list) -> list:
    """Обратное преобразование после data_editor: нормализуем domains.
    Автоматически сохраняет новые домены в domains.json."""
    restored = []
    new_domains = set()
    for row in rows or []:
        if isinstance(row, dict):
            r = dict(row)
            # domains уже список, просто нормализуем
            domains_list = _norm_domains(r.get("domains", []))
            r["domains"] = domains_list
            new_domains.update(domains_list)
            restored.append(r)
        else:
            restored.append(row)
    
    # Обновляем конфиг, если появились новые домены
    existing_domains = set(_load_domains_config())
    if new_domains - existing_domains:
        all_domains = existing_domains | new_domains
        _save_domains_config(list(all_domains))
    
    return restored

def is_new_candidate(uploaded_file):
    if not uploaded_file:
        return False
    last_file = st.session_state.get("last_uploaded_file_name", None)
    return uploaded_file.name != last_file

def clear_candidate_data():
    keys_to_clear = [        
        "filled_json",
        "json_bytes",
        "pdf_bytes",
        "pdf_name",
        "raw_text",
        "pdf_path",
        "projects_experience",
        "profile_summary",
        "v3_summary_text",
        "v3_summary_area",
        "projects_experience_full",
        "projects_editor_ver",
        "project_domains_filter",
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

                # 💾 Автоматически сохраняем все вычисленные данные сразу
                st.session_state["filled_json"] = filled_json
                st.session_state["json_bytes"] = json.dumps(
                    filled_json, indent=2, ensure_ascii=False
                ).encode("utf-8")

                for i in range(56, 76, 2):
                    time.sleep(0.15)
                    progress.progress(i)
                    progress_value = i
                    time_info.text(f"⏱ {round(time.time() - start_time, 1)} Sekunden vergangen")

                # --- Schritt 4: PDF генерировать (einразик) ---
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

                # --- PDF генерировать с правильным именем ---
                output_dir = "data_output"
                os.makedirs(output_dir, exist_ok=True)
                pdf_path = create_pretty_first_section(
                    filled_json, output_dir=output_dir, prefix=pdf_name
                )

                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

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
        # --- Всегда обновляем computed_domains после редактирования проектов ---
        projects_full = edited.get("projects_experience", [])
        project_domains = set(
            d.strip().title()
            for p in projects_full
            if isinstance(p, dict)
            for d in _norm_list(p.get("domains"))
            if str(d).strip()
        )
        config_domains = set(_load_domains_config())
        computed_domains = sorted(config_domains | project_domains)
        st.session_state["computed_domains"] = computed_domains
        edited["computed_domains"] = computed_domains

    # --- Удалено старое поле доменов, теперь актуальное поле только под проектами ---

    with st.expander("Projekte / Erfahrung (projects_experience)", expanded=True):

        if st.button("🪄 Domains автоматически erkennen", key="btn_autofill_project_domains_main"):
            new_domains = set()
            for p in st.session_state.get("projects_experience_full", []):
                if isinstance(p, dict):
                    for d in _norm_list(p.get("domains")):
                        if d:
                            new_domains.add(d.strip().title())
            config_domains = set(_load_domains_config())
            _save_domains_config(sorted(config_domains | new_domains))
            st.success("Domänen wurden автоматиш erkannt и сохранены.")

        # init source-of-truth once
        if "projects_experience_full" not in st.session_state or not isinstance(st.session_state["projects_experience_full"], list):
            st.session_state["projects_experience_full"] = edited.get("projects_experience", []) if isinstance(edited.get("projects_experience"), list) else []

        projects_full = st.session_state["projects_experience_full"]

        # display projects
        display_projects = []
        for p in projects_full:
            if isinstance(p, dict):
                p2 = dict(p)
                p2.pop("__pid", None)
                display_projects.append(p2)
            else:
                display_projects.append(p)

        # editor (stable key!)
        projects_edited = st.data_editor(
            display_projects,
            num_rows="dynamic",
            width="stretch",
            key="ed_projects_experience_main"
        )

        # persist edits
        st.session_state["projects_experience_full"] = projects_edited
        edited["projects_experience"] = projects_edited

        # 1) Собираем домены для фильтра (как есть, без .title())
        all_domains = sorted({
            str(d).strip()
            for p in projects_edited if isinstance(p, dict)
            for d in _norm_list(p.get("domains"))
            if str(d).strip()
        })

        selected_domains = st.multiselect(
            "Filter nach Domänen",
            options=all_domains,
            default=[],
            key="project_domains_filter_main"
        )

        # 2) Фильтруем проекты без учёта регистра
        if selected_domains:
            active = {d.strip().casefold() for d in selected_domains}

            filtered_projects = []
            for p in projects_edited:
                if not isinstance(p, dict):
                    continue
                project_domains = {d.strip().casefold() for d in _norm_list(p.get("domains"))}
                if project_domains & active:
                    filtered_projects.append(p)
        else:
            filtered_projects = projects_edited

        # store for footer button (PDF)
        st.session_state["filtered_projects_for_pdf"] = filtered_projects
        st.session_state["selected_domains_for_pdf"] = selected_domains


        # 3) Domains из отфильтрованных проектов
        domains_out = sorted({
            str(d).strip()
            for p in filtered_projects if isinstance(p, dict)
            for d in _norm_list(p.get("domains"))
            if str(d).strip()
        })

        # 4) Companies/Firmen из отфильтрованных проектов
        companies_out = sorted({
            str(p.get("company", "")).strip()
            for p in filtered_projects
            if isinstance(p, dict) and str(p.get("company", "")).strip()
        })
      
        # 5) Сохраняем списки для PDF (именно списки, не строки)
        st.session_state["pdf_domains_list"] = domains_out
        st.session_state["pdf_companies_list"] = companies_out

        # 6) UI: ключи виджетов (ВАЖНО: state обновляем по этим ключам)
        DOMAINS_UI_KEY = "computed_domains_text_filtered_ui"
        COMPANIES_UI_KEY = "computed_companies_text_filtered_ui"

        st.session_state[DOMAINS_UI_KEY] = ", ".join(domains_out)
        st.session_state[COMPANIES_UI_KEY] = ", ".join(companies_out)

        # 7) Выводим поля ОДИН раз (без value=, иначе может не обновляться)
        st.text_area("Domains", height=60, disabled=True, key=DOMAINS_UI_KEY)
        st.text_area("Firmen",  height=60, disabled=True, key=COMPANIES_UI_KEY)

        # 8) Флаг обновления PDF при изменении фильтра
        st.session_state.setdefault("pdf_needs_refresh", False)
        current_sel = tuple(sorted([s.strip().casefold() for s in selected_domains]))
        if st.session_state.get("pdf_filter_sel") != current_sel:
            st.session_state["pdf_filter_sel"] = current_sel
            st.session_state["pdf_needs_refresh"] = True

# Hard Skills и Skills overview
if "filled_json" in st.session_state:
    edited = dict(st.session_state["filled_json"]) if isinstance(st.session_state["filled_json"], dict) else {}

    # Hard Skills
    if isinstance(edited.get("hard_skills"), dict):
        with st.expander("Fachliche Kompetenzen (Hard Skills)", expanded=False):
            hard_skills_list = [
                {"Kategorie": k, "Werkzeuge": v if isinstance(v, list) else [v]}
                for k, v in edited["hard_skills"].items()
            ]
            hard_skills_edited = st.data_editor(
                hard_skills_list,
                num_rows="dynamic",
                width="stretch",
                key="ed_hard_skills",
                column_config={
                    "Kategorie": st.column_config.TextColumn("Kategorie"),
                    "Werkzeuge": st.column_config.ListColumn("Werkzeuge/Technologien")
                }
            )
            edited["hard_skills"] = {
                row["Kategorie"]: row["Werkzeuge"]
                for row in hard_skills_edited if row.get("Kategorie")
            }

    # Skills overview
    if isinstance(edited.get("skills_overview"), list):
        with st.expander("Kompetenzübersicht (Skills Overview)", expanded=False):
            skills_rows = edited.get("skills_overview", [])
            if not isinstance(skills_rows, list):
                skills_rows = []
            if not skills_rows:
                skills_rows = [{"Kategorie": "", "Werkzeuge": [], "Jahre Erfahrung": ""}]
            # Преобразуем все Werkzeuge к списку
            for row in skills_rows:
                if not isinstance(row.get("Werkzeuge"), list):
                    row["Werkzeuge"] = [row["Werkzeuge"]] if row.get("Werkzeuge") else []
            skills_edited = st.data_editor(
                skills_rows,
                num_rows="dynamic",
                width="stretch",
                key="ed_skills_overview_main",
                column_config={
                    "Kategorie": st.column_config.TextColumn("Kategorie"),
                    "Werkzeuge": st.column_config.ListColumn("Werkzeuge/Technologien"),
                    "Jahre Erfahrung": st.column_config.TextColumn("Jahre Erfahrung")
                }
            )
            edited["skills_overview"] = skills_edited

    # --- Sprachen (languages) ---
    if isinstance(edited.get("languages"), list):
        with st.expander("Sprachen", expanded=False):
            lang_rows = edited.get("languages", [])
            if not isinstance(lang_rows, list):
                lang_rows = []
            if not lang_rows:
                lang_rows = [{"Sprache": "", "Niveau": ""}]
            lang_edited = st.data_editor(
                lang_rows,
                num_rows="dynamic",
                width="stretch",
                key="ed_languages_main",
                column_config={
                    "Sprache": st.column_config.TextColumn("Sprache"),
                    "Niveau": st.column_config.TextColumn("Niveau")
                }
            )
            edited["languages"] = lang_edited
            st.session_state["languages"] = lang_edited

    # --- Ausbildung (Education) ---
    # Гарантируем, что education всегда список для отображения редактора
    if not isinstance(edited.get("education"), list):
        edited["education"] = []
    with st.expander("Ausbildung (Education)", expanded=False):
        edu_rows = edited.get("education", [])
        if not isinstance(edu_rows, list):
            edu_rows = []
        if not edu_rows:
            edu_rows = [{"Institution": "", "Abschluss": "", "Jahr": ""}]
        edu_edited = st.data_editor(
            edu_rows,
            num_rows="dynamic",
            width="stretch",
            key="ed_education_main",
            column_config={
                "Institution": st.column_config.TextColumn("Institution/Universität"),
                "Abschluss": st.column_config.TextColumn("Abschluss/Fachrichtung"),
                "Jahr": st.column_config.TextColumn("Abschlussjahr")
            }
        )
        edited["education"] = edu_edited
        st.session_state["education"] = edu_edited
        if "filled_json" in st.session_state:
            st.session_state["filled_json"]["education"] = edu_edited


pdf_needs_refresh = (last_saved_hash != current_pdf_hash)
st.session_state["pdf_needs_refresh"] = pdf_needs_refresh
st.download_button(

# --- после всех редакторов (Hard Skills / Skills Overview / Summary / Languages etc.) ---
if "filled_json" in st.session_state:
    st.markdown("---")
    st.subheader("⬇️ Ergebnisse herunterladen")

    # PDF-Option — теперь в конце
    use_filter_for_pdf = st.checkbox(
        "Nur gefilterte Projekte ins PDF übernehmen",
        value=True,
        key="use_filter_for_pdf_footer"
    )

    # Гарантируем, что edited определён даже если filled_json нет в session_state
    edited = dict(st.session_state["filled_json"]) if isinstance(st.session_state["filled_json"], dict) else {}

    # Берём актуальные проекты
    projects_full_now = st.session_state.get("projects_experience_full", edited.get("projects_experience", []))
    filtered_projects_now = st.session_state.get("filtered_projects_for_pdf", projects_full_now)
    selected_domains_now = st.session_state.get("selected_domains_for_pdf", [])

    # --- строим "снимок" данных, которые ДОЛЖНЫ попасть в PDF ---
    pdf_preview = dict(edited)

    if use_filter_for_pdf and selected_domains_now:
        pdf_preview["projects_experience"] = filtered_projects_now
        pdf_preview["domains"] = st.session_state.get("pdf_domains_list", [])
        pdf_preview["companies"] = st.session_state.get("pdf_companies_list", [])
    else:
        pdf_preview["projects_experience"] = projects_full_now
        # domains/companies считаем из полного списка проектов
        pdf_preview["domains"] = sorted({
            str(d).strip()
            for p in projects_full_now if isinstance(p, dict)
            for d in _norm_list(p.get("domains"))
            if str(d).strip()
        })
        pdf_preview["companies"] = sorted({
            str(p.get("company", "")).strip()
            for p in projects_full_now
            if isinstance(p, dict) and str(p.get("company", "")).strip()
        })

    # title safety
    if not pdf_preview.get("title"):
        pdf_preview["title"] = pdf_preview.get("position") or pdf_preview.get("role") or ""

    current_pdf_hash = _stable_hash(pdf_preview)
    last_saved_hash = st.session_state.get("last_saved_pdf_hash")

    pdf_needs_refresh = (last_saved_hash != current_pdf_hash)
    st.session_state["pdf_needs_refresh"] = pdf_needs_refresh

    if pdf_needs_refresh:
        st.warning("PDF ist nicht aktuell. Bitte klicke auf „Änderungen speichern & PDF aktualisieren“.")

    # --- ЕДИНСТВЕННАЯ КНОПКА: сохранить всё + обновить PDF ---
    if st.button("💾 Änderungen speichern & PDF aktualisieren", key="btn_save_all_and_pdf_footer"):
        # 1) сохраняем финальный JSON (всегда полный, без фильтра — чтобы JSON был “истиной”)
        final_json = dict(edited)
        final_json["projects_experience"] = projects_full_now

        st.session_state["filled_json"] = final_json
        st.session_state["json_bytes"] = json.dumps(final_json, indent=2, ensure_ascii=False).encode("utf-8")

        # 2) создаём PDF по pdf_preview (уже с учётом фильтра/без фильтра)
        pdf_json = dict(pdf_preview)

        # Удаляем пустые поля перед генерацией PDF
        def _remove_empty_fields(d):
            if isinstance(d, dict):
                return {k: _remove_empty_fields(v) for k, v in d.items() if v not in (None, "", [], {})}
            elif isinstance(d, list):
                return [ _remove_empty_fields(x) for x in d if x not in (None, "", [], {}) ]
            else:
                return d
        pdf_json = _remove_empty_fields(pdf_json)

        if not pdf_json.get("title"):
            pdf_json["title"] = pdf_json.get("position") or pdf_json.get("role") or ""

        output_dir = "data_output"
        os.makedirs(output_dir, exist_ok=True)

        pdf_name = st.session_state.get("pdf_name", "CV_Streamlit")

        pdf_path = create_pretty_first_section(pdf_json, output_dir=output_dir, prefix=pdf_name)
        with open(pdf_path, "rb") as f:
            st.session_state["pdf_bytes"] = f.read()

        # 3) помечаем PDF как актуальный
        st.session_state["last_saved_pdf_hash"] = current_pdf_hash
        st.session_state["pdf_needs_refresh"] = False
        st.success("Alle Änderungen wurden gespeichert und das PDF wurde aktualisiert.")

    # --- Downloads ---
    pdf_name = st.session_state.get("pdf_name", "CV_Streamlit")

    st.download_button(
        label="📘 JSON herunterladen",
        data=st.session_state.get("json_bytes", b""),
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
            key="download_pdf",
            disabled=st.session_state.get("pdf_needs_refresh", False)
        )


