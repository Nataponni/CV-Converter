from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepInFrame
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
for key in ["Normal", "Title", "Heading2", "Heading3"]:
    styles[key].fontName = BASE_FONT
styles["Title"].fontName = BOLD_FONT
styles["Heading2"].fontName = BOLD_FONT
styles["Heading3"].fontName = BOLD_FONT

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

def make_overview_box(data, styles):
    hard_skills = data.get("hard_skills", {})
    if not hard_skills:
        return None

    rows = [[Paragraph("<b>Overview</b>", styles["Heading3"]), ""]]

    # --- Гибкий порядок ---
    desired_order = [
        "monitoring_security",
        "containers_orchestration",
        "programming_languages",
        "devops_iac",
        "databases",
        "security",
        "other_tools"
    ]

    # Сначала добавляем ключи из desired_order
    for key in desired_order:
        tools = hard_skills.get(key, [])
        if tools:
            left = Paragraph(f"<b>{format_category_name(key)}:</b>", styles["Normal"])
            right = Paragraph(", ".join(sorted(set(tools))), styles["Normal"])
            rows.append([left, right])

    # Затем добавляем все остальные ключи
    for key, tools in hard_skills.items():
        if key not in desired_order and tools:
            left = Paragraph(f"<b>{format_category_name(key)}:</b>", styles["Normal"])
            right = Paragraph(", ".join(sorted(set(tools))), styles["Normal"])
            rows.append([left, right])

    # Создаём таблицу и стили
    table = Table(rows, colWidths=[55 * mm, None], hAlign="LEFT")
    style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("FONTNAME", (0,0), (-1,0), BOLD_FONT),
    ])
    for i in range(1, len(rows)):
        bg = colors.whitesmoke if i % 2 == 0 else colors.white
        style.add("BACKGROUND", (0,i), (-1,i), bg)
    table.setStyle(style)

    return table


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

    # Заголовок
    role = json_data.get("title", "")
    title_line = " – ".join([t for t in [role, full_name] if t])
    elements.append(p(f"<b>{title_line or 'Curriculum Vitae'}</b>", styles["Title"]))
    elements.append(Spacer(1, 8))

    # Левая + правая колонка
    left_box = make_left_box(json_data, styles)
    right_box = make_right_box(json_data, styles)

    page_width, _ = A4
    usable = page_width - doc.leftMargin - doc.rightMargin
    left_w = 60 * mm
    right_w = usable - left_w

    table = Table([[left_box, right_box]], colWidths=[left_w, right_w], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 12))

    # Overview (на основе hard_skills)
    overview_box = make_overview_box(json_data, styles)
    if overview_box:
        elements.append(overview_box)

    doc.build(elements)
    return out_path

# --- Запуск ---
if __name__ == "__main__":
    with open("data_output/result_2_test.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    pdf_path = create_pretty_first_section(data)
    print(f"✅ PDF создан: {pdf_path}")
