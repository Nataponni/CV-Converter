import streamlit as st
import json, os, tempfile, time
import threading
import uuid
from pdf_processor import prepare_cv_text
from chatgpt_client import ask_chatgpt
from postprocess import postprocess_filled_cv, normalize_project_domains
from cv_pdf_generator import create_pretty_first_section

# --- Seiteneinstellungen ---
st.set_page_config(page_title="CV-Konverter", page_icon="📄")
st.title("📄 CV-Konverter")

# 1️⃣ Datei-Upload
uploaded_file = st.file_uploader("Wähle eine PDF-Datei aus", type=["pdf"])

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
            json.dump({"domains": sorted(set(domains))}, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка при сохранении доменов: {e}")
        return False


def _collect_domains(projects: list) -> list[str]:
    """Собирает домены из проектов + предустановленные из конфига."""
    out = set()
    # Домены из проектов
    for p in projects or []:
        if isinstance(p, dict):
            for d in _norm_list(p.get("domains")):
                if d:
                    out.add(d)
    # Домены из конфига
    config_domains = _load_domains_config()
    out.update(config_domains)
    return sorted(out)


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
    """Подготовка проектов для data_editor: оставляем domains как список."""
    display = []
    for p in projects or []:
        if isinstance(p, dict):
            row = dict(p)
            # Оставляем domains как список для отображения тегами
            row["domains"] = _norm_domains(row.get("domains", []))
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

            # --- Canonical projects list for this section (source of truth) ---
            if "projects_experience_full" not in st.session_state or not isinstance(st.session_state.get("projects_experience_full"), list):
                st.session_state["projects_experience_full"] = edited.get("projects_experience", [])
            projects_full = st.session_state.get("projects_experience_full", [])
            if not isinstance(projects_full, list):
                projects_full = []
                st.session_state["projects_experience_full"] = projects_full

            # --- force re-render of data_editor when we programmatically change data ---
            st.session_state.setdefault("projects_editor_ver", 0)

            # --- ensure stable per-row id (needed to merge edits from filtered view back into full list) ---
            changed = False
            new_full = []
            for p in projects_full:
                if isinstance(p, dict) and "__pid" not in p:
                    p = dict(p)
                    p["__pid"] = str(uuid.uuid4())
                    changed = True
                new_full.append(p)
            projects_full = new_full
            if changed:
                st.session_state["projects_experience_full"] = projects_full

            # --- Action: auto-detect domains (no GPT), then immediately re-render table ---
            if st.button("🪄 Domains automatisch erkennen", key="btn_autofill_project_domains"):
                updated = []
                for p in projects_full:
                    if isinstance(p, dict):
                        p2 = dict(p)  # avoid in-place mutation
                        p2["domains"] = normalize_project_domains(p2)
                        updated.append(p2)
                    else:
                        updated.append(p)

                st.session_state["projects_experience_full"] = updated
                st.session_state["projects_editor_ver"] += 1
                st.session_state["domains_updated_msg"] = True
                st.rerun()

            if st.session_state.pop("domains_updated_msg", False):
                st.success("Domains aktualisiert")
            
            projects_full = st.session_state.get("projects_experience_full", [])
            if not isinstance(projects_full, list):
                projects_full = []
                st.session_state["projects_experience_full"] = projects_full

            # --- Filter (live) ---
            # --- Filter state (for table) ---
            all_domains_for_filter = _collect_domains(projects_full)

            selected_project_domains = st.session_state.get("project_domains_filter") or []
            selected_project_domains = [x for x in selected_project_domains if x in all_domains_for_filter]
            st.session_state["project_domains_filter"] = selected_project_domains

            # если фильтр изменился -> пересоздаём data_editor (иначе он может держать старое состояние)
            curr_filter = tuple(sorted(selected_project_domains))
            prev_filter = st.session_state.get("__prev_project_domains_filter")
            if prev_filter != curr_filter:
                st.session_state["__prev_project_domains_filter"] = curr_filter
                st.session_state["projects_editor_ver"] += 1

            editor_key = f"ed_projects_experience_{st.session_state['projects_editor_ver']}"

            # --- формируем данные для одной таблицы ---
            is_filtered_view = bool(selected_project_domains)
            if is_filtered_view:
                selected_set = set(map(str, selected_project_domains))
                display_projects = [
                    p for p in projects_full
                    if isinstance(p, dict)
                    and set(map(str, p.get("domains", []) if isinstance(p.get("domains", []), list) else []))
                        .intersection(selected_set)
                ]
            else:
                display_projects = projects_full

            # спрятать __pid в таблице (важно: Streamlit скрывает колонки, которых нет в column_order)
            col_order = []
            for p in display_projects:
                if isinstance(p, dict):
                    for k in p.keys():
                        if k != "__pid" and k not in col_order:
                            col_order.append(k)

            num_rows_mode = "fixed" if is_filtered_view else "dynamic"
            all_domains_for_filter = _collect_domains(projects_full)

            # фильтр пока НЕ рисуем (рисуем после таблицы), но состояние читаем
            selected_project_domains = st.session_state.get("project_domains_filter") or []
            selected_project_domains = [x for x in selected_project_domains if x in all_domains_for_filter]
            st.session_state["project_domains_filter"] = selected_project_domains

            is_filtered_view = bool(selected_project_domains)
            if is_filtered_view:
                selected_set = set(map(str, selected_project_domains))
                display_projects = [
                    p for p in projects_full
                    if isinstance(p, dict)
                    and set(map(str, _norm_list(p.get("domains")))).intersection(selected_set)
                ]
            else:
                display_projects = projects_full

            # --- data_editor ---
            # Домены отображаются как список тегов (как stack)
            display_projects_editable = _projects_to_display(display_projects)

            domains_col = st.column_config.ListColumn(
                "domains",
                help="Domänen als Tags",
                width="medium",
            )

            edited_display = st.data_editor(
                display_projects_editable,
                num_rows=("fixed" if is_filtered_view else "dynamic"),
                width="stretch",
                key=editor_key,
                column_order=col_order if col_order else None,
                column_config={"domains": domains_col},
            )

            edited_display = _projects_from_display(_as_records(edited_display) or [])


            # IMPORTANT: в filtered-view __pid может не вернуться из data_editor — восстановим по позиции
            if is_filtered_view:
                fixed = []
                for src_row, ed_row in zip(display_projects, edited_display):
                    if isinstance(src_row, dict) and isinstance(ed_row, dict):
                        ed_row = dict(ed_row)

                        if "__pid" in src_row and "__pid" not in ed_row:
                            ed_row["__pid"] = src_row["__pid"]

                        if "domains" not in ed_row and "domains" in src_row:
                            ed_row["domains"] = src_row.get("domains", [])

                    fixed.append(ed_row)
                edited_display = fixed

            # --- merge обратно в projects_full (если фильтр включён) ---
            if is_filtered_view:
                full_by_pid = {
                    p["__pid"]: p
                    for p in projects_full
                    if isinstance(p, dict) and "__pid" in p
                }

                for p in (edited_display or []):
                    if isinstance(p, dict) and "__pid" in p:
                        pid = p["__pid"]
                        base = full_by_pid.get(pid, {})
                        if not isinstance(base, dict):
                            base = {}

                        merged = dict(base)
                        merged.update(p)
                        merged["__pid"] = pid

                        if "domains" not in p and "domains" in base:
                            merged["domains"] = base.get("domains", [])

                        full_by_pid[pid] = merged

                merged_full = []  # <-- ВОТ ЭТО ДОБАВИТЬ
                for p in projects_full:
                    if isinstance(p, dict) and "__pid" in p and p["__pid"] in full_by_pid:
                        merged_full.append(full_by_pid[p["__pid"]])
                    else:
                        merged_full.append(p)

                projects_full = merged_full
            else:
                # no-filter: просто берём то, что вернул редактор
                if isinstance(edited_display, list):
                    projects_full = edited_display


            # source of truth
            st.session_state["projects_experience_full"] = projects_full
            edited["projects_experience"] = projects_full

            # пересчёт options: домены из проектов + конфиг (чтобы новые домены поялись)
            all_available_domains = _collect_domains(projects_full)
            # но фильтруем по тому, что реально есть в текущих проектах
            project_domains = _collect_project_domains_only(projects_full)
            display_domains_for_filter = sorted(set(all_available_domains) & set(project_domains))

            # подчистить фильтр (иначе multiselect может падать)
            st.session_state["project_domains_filter"] = [
                x for x in (st.session_state.get("project_domains_filter") or [])
                if x in display_domains_for_filter
            ]

            # рисуем фильтр ПОСЛЕ таблицы (как ты хочешь)
            st.multiselect(
                "Projekt-Filter nach Domains",
                options=display_domains_for_filter,
                key="project_domains_filter",
            )

            # сохраняем текущий VIEW (что сейчас “выбрано” для вывода)
            active_filter = st.session_state.get("project_domains_filter") or []
            if active_filter:
                active_set = set(map(str, active_filter))
                projects_view = [
                    p for p in projects_full
                    if isinstance(p, dict)
                    and set(map(str, _norm_list(p.get("domains")))).intersection(active_set)
                ]
            else:
                projects_view = projects_full

            st.session_state["projects_experience_view"] = projects_view

        # Domänen (aus Projekten berechnet) — по текущему VIEW, если есть
        src_projects = projects_view if isinstance(projects_view, list) else projects_full
        computed_domains = sorted({
            d.strip().title()
            for p in (src_projects or [])
            if isinstance(p, dict)
            for d in _norm_list(p.get("domains"))
            if str(d).strip()
        })
        edited["domains"] = computed_domains

        # Отображение доменов в текстовом поле (как было в начале)
        st.session_state["domains_computed_text"] = ", ".join(computed_domains)
        st.text_area(
            "Domänen (aus Projekten berechnet)",
            value=st.session_state["domains_computed_text"],
            height=80,
            disabled=True,
            key="domains_computed_text",
        )


    else:
        # Альтернативные ключи, если структура иная
        for exp_key in ["experience", "work_experience", "jobs"]:
            if isinstance(edited.get(exp_key), list):
                with st.expander("Berufserfahrung", expanded=False):
                    edited[exp_key] = st.data_editor(
                        edited[exp_key],
                        num_rows="dynamic",
                        width="stretch",
                        key=f"ed_{exp_key}"
                    )
                break


    # Образование: поддержка строкового поля или списка объектов
    if isinstance(edited.get("education"), list):
        with st.expander("Ausbildung (education)", expanded=False):
            edited["education"] = st.data_editor(
                edited["education"],
                num_rows="dynamic",
                width="stretch",
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
                width="stretch",
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
                width="stretch",
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


    # Кнопки управления
    if st.button("💾 Änderungen speichern & PDF erzeugen", key="save_and_regen"):

        # 0) Берём проекты для экспорта: сначала view (фильтр), иначе full, иначе из edited
        projects_for_export = st.session_state.get("projects_experience_view")
        if projects_for_export is None:
            projects_for_export = st.session_state.get("projects_experience_full")

        if projects_for_export is None:
            projects_for_export = edited.get("projects_experience", [])

        # Streamlit может вернуть DataFrame-like — приводим к list[dict]
        if hasattr(projects_for_export, "to_dict"):
            try:
                projects_for_export = projects_for_export.to_dict(orient="records")
            except Exception:
                pass

        if not isinstance(projects_for_export, list):
            projects_for_export = []

        # 1) Чистим служебные ключи (например "__pid") и нормализуем domains
        cleaned_projects = []
        for p in projects_for_export:
            if isinstance(p, dict):
                p2 = {k: v for k, v in p.items() if not str(k).startswith("__")}

                # domains -> всегда list[str]
                dom = p2.get("domains", [])
                if isinstance(dom, str):
                    dom = [x.strip() for x in dom.split(",") if x.strip()]
                elif not isinstance(dom, list):
                    dom = []
                p2["domains"] = [str(x).strip() for x in dom if str(x).strip()]

                cleaned_projects.append(p2)
            else:
                # если вдруг попалась не-dict строка/что-то — пропускаем
                continue

        edited["projects_experience"] = cleaned_projects

        # 2) Пересчитать domains из тех проектов, которые реально экспортируем
        computed_domains = sorted({
            d.strip().title()
            for p in cleaned_projects
            if isinstance(p, dict)
            for d in (p.get("domains", []) if isinstance(p.get("domains", []), list) else [])
            if str(d).strip()
        })
        edited["domains"] = computed_domains

        # 3) Остальная логика сохранения JSON
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

        # 4) Генерация PDF
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
