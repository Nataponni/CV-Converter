from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepInFrame, KeepTogether, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from datetime import date
import re
import os
import json

# Регистрация шрифтов
pdfmetrics.registerFont(TTFont("Roboto", "fonts/Roboto-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Roboto-Bold", "fonts/Roboto-Bold.ttf"))
BASE_FONT = "Roboto"
BOLD_FONT = "Roboto-Bold"

styles = getSampleStyleSheet()

# --- Базовый размер шрифта и гарнитура ---
BASE_FONT_SIZE = 11     # Было 10, теперь читается лучше
HEADING_FONT_SIZE = 14  # Для подзаголовков
TITLE_FONT_SIZE = 24    # Для основного заголовка

# --- Базовые шрифты для всех ключевых стилей ---
for key in ["Normal", "Title", "Heading2", "Heading3"]:
    styles[key].fontName = BASE_FONT

# --- Конкретные настройки ---
styles["Normal"].fontSize = BASE_FONT_SIZE
styles["Normal"].leading = BASE_FONT_SIZE + 2  # межстрочный интервал

styles["Title"].fontName = BOLD_FONT
styles["Title"].fontSize = TITLE_FONT_SIZE
styles["Title"].leading = TITLE_FONT_SIZE + 2
styles["Title"].spaceAfter = 8

styles["Heading2"].fontName = BOLD_FONT
styles["Heading2"].fontSize = HEADING_FONT_SIZE
styles["Heading2"].leading = HEADING_FONT_SIZE + 2
styles["Heading2"].spaceAfter = 6

styles["Heading3"].fontName = BOLD_FONT
styles["Heading3"].fontSize = HEADING_FONT_SIZE
styles["Heading3"].leading = HEADING_FONT_SIZE + 1
styles["Heading3"].spaceAfter = 4

# --- ДОБАВЬ ПРЕМИУМ СТИЛЬ ---

FIRM_COLOR = colors.HexColor("#2196F3")  # Голубой фирменный цвет
# LOGO_PATH = "logo.png"  # Путь к логотипу (замени на свой)

# Премиальные стили карточек проектов
project_card_title_style = ParagraphStyle(
    "ProjectCardTitle",
    parent=styles["Heading3"],
    fontName=BOLD_FONT,
    fontSize=16,   # 🔹 было 15
    leading=20,
    textColor=colors.HexColor("#222e3a"),
    spaceAfter=6,
)
project_card_role_style = ParagraphStyle(
    "ProjectCardRole",
    parent=styles["Normal"],
    fontSize=11,
    textColor=colors.HexColor("#888888"),
    leftIndent=2,
)
project_card_desc_style = ParagraphStyle(
    "ProjectCardDesc",
    parent=styles["Normal"],
    fontSize=11,
    textColor=colors.HexColor("#6c7a89"),
    spaceAfter=4,
)
project_card_stack_style = ParagraphStyle(
    "ProjectCardStack",
    parent=styles["Normal"],
    fontSize=10,
    textColor=FIRM_COLOR,
    italic=True,
    spaceAfter=2,
)


# --- Утилиты ---
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()) or "Unknown"

def p(text, style):
    return Paragraph(text.replace("\n", "<br/>"), style)

def format_category_name(key: str) -> str:
    return {
        "cloud_platforms": "Cloud Platforms",
        "devops_iac": "DevOps & IaC",
        "monitoring_security": "Monitoring & Security",
        "programming_languages": "Programming Languages",
        "containers_orchestration": "Containers & Orchestration",
        "ci_cd_tools": "CI/CD Tools",
        "databases": "Databases",
        "backend": "Backend",
        "frontend": "Frontend",
        "security": "Security",
        "ai_ml_tools": "AI & ML Tools",
        "infrastructure_os": "Infrastructure & OS",
        "other_tools": "Other Tools"
    }.get(key, key.replace("_", " ").title())

# --- Блоки PDF ---
def make_left_box(data, styles):
    items = []
    header_style = ParagraphStyle("LeftHeader", parent=styles["Heading3"], fontName=BOLD_FONT, spaceAfter=6)

    # Education
    edu = data.get("education", "")
    if edu:
        items += [p("<b>Education:</b>", header_style), p(edu, styles["Normal"]), Spacer(0, 6)]

    # Languages
    langs = data.get("languages", [])
    if langs:
        items.append(p("<b>Languages:</b>", header_style))
        for lang in langs:
            lang_name = lang.get("language", "")
            lvl  = lang.get("level", "")
            if lang_name and lvl:
                items.append(Paragraph(f"{lang_name} &mdash; {lvl}", styles["Normal"]))
            elif lang_name:
                items.append(p(f"• {lang_name}", styles["Normal"]))
        items.append(Spacer(0, 6))

    # Domains
    dom = data.get("domains", [])
    if dom:
        items.append(p("<b>Domains:</b>", header_style))
        items.append(p("<br/>".join(dom), styles["Normal"]))

    return KeepInFrame(0, 0, items, mode="shrink")

def make_right_box(data, styles):
    text = data.get("profile_summary", "") or ""
    body = [p(text, ParagraphStyle("Summary", parent=styles["Normal"], leading=16))]
    return KeepInFrame(0, 0, body, mode="shrink")

    # --- Заголовок блока ---
def make_overview_box(data, styles):
    hard_skills = data.get("hard_skills", {})
    if not hard_skills:
        return None

    # Заголовок
    title_style = ParagraphStyle(
        "OverviewTitle",
        parent=styles["Heading2"],
        fontName=BOLD_FONT,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#2196F3"),
        spaceBefore=10,
        spaceAfter=16
    )

    rows = [[Paragraph("OVERVIEW –<br/> Hard Skills", title_style), ""]]
    rows.append(["", ""])  # отступ после заголовка

    desired_order = [
        "programming_languages", "backend", "frontend", "databases",
        "data_engineering", "etl_tools", "bi_tools", "analytics",
        "cloud_platforms", "devops_iac", "ci_cd_tools",
        "containers_orchestration", "monitoring_security",
        "security", "ai_ml_tools", "infrastructure_os", "other_tools"
    ]

    for key in desired_order:
        tools = hard_skills.get(key, [])
        if not tools:
            continue

        tool_names = []
        for t in tools:
            if isinstance(t, dict):
                name = t.get("name", "").strip()
                if name:
                    tool_names.append(name)
            elif isinstance(t, str):
                tool_names.append(t.strip())

        if not tool_names:
            continue

        tool_names = sorted(set(tool_names))

        left = Paragraph(f"<b>{format_category_name(key)}:</b>",
                         ParagraphStyle("Left", parent=styles["Normal"], fontName=BOLD_FONT, fontSize=11))
        right = Paragraph(", ".join(tool_names),
                          ParagraphStyle("Right", parent=styles["Normal"], fontSize=11, wordWrap="None"))  # ❗ одна строка
        rows.append([left, right])

    # Таблица с зеброй
    table = Table(rows, colWidths=[55*mm, 120*mm], hAlign="LEFT")
    style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 14),
    ])

    # Чередование серых строк
    for i in range(2, len(rows)):
        bg = colors.whitesmoke if i % 2 == 0 else colors.white
        style.add("BACKGROUND", (0, i), (-1, i), bg)

    table.setStyle(style)
    return table


def make_first_page_section(data, styles):
    """
    Персональный блок в премиальном стиле, с левой колонкой и увеличенным шрифтом.
    """
    elements = []

    full_name = data.get("full_name", "")
    position = data.get("title", "")
    location = data.get("location", "")
    email = data.get("email", "")
    phone = data.get("phone", "")

    # --- Левая колонка (Education, Languages, Domains) ---
    left_box = make_left_box(data, styles)

    # --- Правая колонка (Profile Summary) ---
    right_box = make_right_box(data, styles)

    left_w = 70 * mm
    right_w = 90 * mm

    table = Table([[left_box, right_box]], colWidths=[left_w, right_w], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # --- Заголовок (имя и должность, увеличенный шрифт) ---
    header = f'<b>{full_name}</b>'
    if position:
        header += f'<br/><font color="#888888">{position}</font>'
    header_p = Paragraph(header, ParagraphStyle(
        "CardTitleBig",
        parent=styles["Title"],
        fontName=BOLD_FONT,
        fontSize=28,
        leading=32,
        spaceAfter=14,
        textColor=colors.HexColor("#2196F3"),
    ))

    # --- Контакты ---
    contact_lines = []
    if location:
        contact_lines.append(f'<font color="#888888">{location}</font>')
    if email:
        contact_lines.append(f'<font color="#888888">{email}</font>')
    if phone:
        contact_lines.append(f'<font color="#888888">{phone}</font>')
    contact_p = Paragraph(
        "<br/>".join(contact_lines),
        ParagraphStyle(
            "ContactInfoBig",
            parent=styles["Normal"],
            fontSize=14,
            leading=20,
            spaceAfter=12,
            textColor=colors.HexColor("#888888"),
        )
    )

    # --- Сборка первой страницы ---
    elements.append(header_p)
    elements.append(contact_p)
    elements.append(Spacer(1, 18))
    elements.append(table)
    elements.append(Spacer(1, 28))

    return elements



def make_projects_section(projects, styles):
    if not projects:
        return []

    elements = []
    section_title = Paragraph(
        '<font color="#2196F3"><b>PROJECTS & EXPERIENCE</b></font>',
        ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=18,
            leading=22,
            spaceAfter=14,
            textColor=colors.HexColor("#2196F3"),
        )
    )
    elements += [section_title, Spacer(1, 18)]

    cards_on_page = 0
    for idx, project in enumerate(projects, 1):
        title = project.get("project_title", "")
        role = project.get("role", "")
        overview = project.get("overview", "")
        duration = project.get("duration", "")
        tech_stack = project.get("tech_stack", [])
        responsibilities = project.get("responsibilities", [])

        # Заголовок
        header = f'<b>Project {idx}. {title}</b>'
        if role:
            header += f'<br/><font color="#888888">{role}</font>'
        if duration:
            header += f'<br/><font color="#2196F3">{duration}</font>'
        header_p = Paragraph(header, ParagraphStyle(
            "CardTitle",
            parent=styles["Heading3"],
            fontSize=15,
            leading=20,
            spaceAfter=10,
            textColor=colors.HexColor("#222e3a"),
        ))

        # Описание
        desc_p = Paragraph(overview, ParagraphStyle(
            "CardDesc",
            parent=styles["Normal"],
            fontSize=10,
            leading=11,
            spaceAfter=2,
            textColor=colors.HexColor("#6c7a89"),
        )) if overview else None

        # Responsibilities (каждый пункт отдельным Paragraph)

        resp_items = []
        if responsibilities:
            resp_items.append(Paragraph(
                '<b><font color="#2196F3">Responsibilities:</font></b>',   # 🔹 жирный и синий заголовок
                ParagraphStyle(
                    "CardRespTitle",
                    parent=styles["Normal"],
                    fontSize=10,
                    leading=11,
                    spaceAfter=2,
                    textColor=FIRM_COLOR,
                )
            ))
            for r in responsibilities:
                resp_items.append(Paragraph(
                    f'• {r}',
                    ParagraphStyle(
                        "CardRespItem",
                        parent=styles["Normal"],
                        fontSize=10,
                        leading=11,
                        leftIndent=24,      # отступ для всей строки
                        firstLineIndent=-10, # 🔹 сдвигаем только первую строку (чтобы точка осталась слева)
                        spaceAfter=0,
                        textColor=colors.HexColor("#222e3a"),
                    )
        ))

        # Tech stack (в строку)
        stack_p = None
        if tech_stack:
            stack = " · ".join(tech_stack)
            stack_p = Paragraph(
                f'<font color="#2196F3"><b>Tech stack:</b> {stack}</font>',
                ParagraphStyle(
                    "CardStack",
                    parent=styles["Normal"],
                    fontSize=11,
                    leading=12,
                    spaceAfter=0,
                    textColor=colors.HexColor("#2196F3"),
                )
            )

        # Содержимое карточки
        card_content = [header_p]
        if desc_p:
            card_content.append(desc_p)
        if resp_items:
            card_content.extend(resp_items)
        if stack_p:
            card_content.append(Spacer(1, 10))
            card_content.append(stack_p)

        card_table = Table([[KeepInFrame(0, 170 * mm, card_content, mode="truncate")]],
            colWidths=[170 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#2196F3")),
                ("ROUNDED", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 24),
                ("RIGHTPADDING", (0, 0), (-1, -1), 24),
                ("TOPPADDING", (0, 0), (-1, -1), 20),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
                ("SHADOW", (0, 0), (-1, -1), colors.HexColor("#bfe3ff"), 6, -6),
            ])
        )

        elements.append(Spacer(1, 0))
        elements.append(card_table)
        elements.append(Spacer(1, 10))
        cards_on_page += 1

        # После двух карточек — новая страница
        if cards_on_page == 2:
            elements.append(PageBreak())
            cards_on_page = 0

    return elements

import re

def parse_years(value):
    """
    Приводит years_of_experience к числу.
    Поддерживает строки вида '5+ years', '8 years', '', а также int.
    """
    if not value:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group())
    return 0


def make_skills_overview_box(data, styles):
    skills_overview = data.get("skills_overview", [])
    if not skills_overview:
        return None

    # Заголовок
    title = Paragraph(
        '<font color="#2196F3"><b>SKILLS OVERVIEW</b></font>',
        ParagraphStyle(
            "SkillsOverviewTitle",
            parent=styles["Heading2"],
            fontSize=18,
            leading=22,
            spaceAfter=16,
            textColor=colors.HexColor("#2196F3"),
        )
    )

    # Группируем по категориям
    grouped = {}
    for item in skills_overview:
        cat = item.get("category", "").strip()
        tool = item.get("tool", "").strip()
        years = parse_years(item.get("years_of_experience", 0))

        if cat not in grouped:
            grouped[cat] = {"tools": [], "max_years": 0}

        if tool:
            grouped[cat]["tools"].append(tool)

        grouped[cat]["max_years"] = max(grouped[cat]["max_years"], years)

    # Заголовки таблицы
    rows = [[
        Paragraph("<b>Category</b>", styles["Normal"]),
        Paragraph("<b>Tools</b>", styles["Normal"]),
        Paragraph("<b>YoE</b>", styles["Normal"])
    ]]

    # Данные
    for cat, values in grouped.items():
        tools = ", ".join(sorted(set(values["tools"])))
        years = str(values["max_years"])
        cat_name = format_category_name(cat)  # 👈 нормализуем название категории

        rows.append([
            Paragraph(cat_name, styles["Normal"]),
            Paragraph(tools, styles["Normal"]),
            Paragraph(years, ParagraphStyle("YoE", parent=styles["Normal"], alignment=1))
        ])

    # Таблица
    table = Table(rows, colWidths=[60*mm, 80*mm, 30*mm], hAlign="LEFT")

    style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f2fc")),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ])

    # Зебра
    for i in range(1, len(rows)):
        bg = colors.whitesmoke if i % 2 == 0 else colors.white
        style.add("BACKGROUND", (0, i), (-1, i), bg)

    table.setStyle(style)
    return [title, Spacer(1, 8), table, Spacer(1, 16)]



# --- Главная сборка ---
def create_pretty_first_section(json_data, output_dir=".", prefix="CV"):
    full_name = json_data.get("full_name", "Unknown")
    safe = sanitize_filename(full_name)
    fname = f"{prefix}_{safe}_{date.today().isoformat()}.pdf"
    out_path = os.path.join(output_dir, fname)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    elements = []

    # --- Персональный блок с левой колонкой и премиальным стилем ---
    elements += make_first_page_section(json_data, styles)

    # --- Overview (Hard Skills) ---
    overview_box = make_overview_box(json_data, styles)
    if overview_box:
        elements.append(overview_box)


    # --- Projects Section ---
    projects_section = make_projects_section(json_data.get("projects_experience", []), styles)
    elements += projects_section

    # --- Skill Overview ---
    skills_overview_box = make_skills_overview_box(json_data, styles)
    if skills_overview_box:
        elements += skills_overview_box



    doc.build(elements)
    return out_path

# --- Запуск ---
if __name__ == "__main__":
    with open("data_output/result_2.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    pdf_path = create_pretty_first_section(data)
    print(f"✅ PDF создан: {pdf_path}")
