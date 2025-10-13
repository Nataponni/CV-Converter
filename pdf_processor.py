import fitz  # PyMuPDF
import re


def extract_text_by_page(pdf_path):
    """Extracts text page-by-page from a PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text().strip() for page in doc]
    doc.close()
    return pages_text


def clean_text(text):
    """Normalize and tag known sections like [DOMAINS], [EDUCATION], etc."""
    text = re.sub(r"\[\d+\]|\(\d+\)", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    section_markers = {
        r"(?i)(?<=\n)(Domains:?)": "[DOMAINS]",
        r"(?i)(Languages:?)": "[LANGUAGES]",
        r"(?i)(Education:?)": "[EDUCATION]",
        r"(?i)(Profile|Summary|About Me|Professional Summary)": "[PROFILE_SUMMARY]",
        r"(?i)(Projects:?)": "[PROJECTS]",
        r"(?i)(Skills|Professional skills|Technical skills):?": "[SKILLS]",
    }

    for pattern, marker in section_markers.items():
        text = re.sub(pattern, f"\n{marker}\n\\1", text)

    # Add closing tags
    for tag in ["DOMAINS", "SKILLS", "LANGUAGES", "EDUCATION", "PROJECTS", "PROFILE_SUMMARY"]:
        text = re.sub(
            rf"\[{tag}\](.*?)\n(?=\[|\Z)",
            rf"[{tag}]\1[/{tag}]\n",
            text,
            flags=re.DOTALL,
        )

    return text.strip()


def clean_responsibilities(responsibilities, max_words=18, max_items=6):
    """
    Очищает и сокращает список 'responsibilities':
    - Удаляет фразы типа "responsible for", "involved in" и т.п.
    - Сокращает слишком длинные пункты до max_words.
    - Делает текст лаконичным, но сохраняет смысл.
    - Ограничивает количество пунктов до max_items.
    """
    cleaned = []
    for i, resp in enumerate(responsibilities):
        if i >= max_items:
            break  # ограничение по числу пунктов

        # базовая очистка
        resp = resp.strip().rstrip(".;:")

        # удаляем вводные фразы (responsible for, participated in и т.п.)
        resp = re.sub(
            r"(?i)\b(responsible\s+for|involved\s+in|participated\s+in|helped\s+to|tasked\s+with|working\s+on|assist(ed)?\s+in|support(ed)?\s+with)\b",
            "",
            resp,
        ).strip()

        # сокращаем слишком длинные пункты
        words = resp.split()
        if len(words) > max_words:
            resp = " ".join(words[:max_words]) + "..."

        # чистим повторяющиеся пробелы
        resp = re.sub(r"\s{2,}", " ", resp)

        # делаем первую букву заглавной
        if resp:
            cleaned.append(resp[0].upper() + resp[1:])

    return cleaned



def extract_domains_from_text(text):
    """Extract exact values inside [DOMAINS] ... [/DOMAINS]."""
    match = re.search(r"\[DOMAINS\](.*?)\[/DOMAINS\]", text, re.DOTALL)
    if not match:
        return []
    lines = match.group(1).split("\n")
    return [line.strip() for line in lines if line.strip()]


def extract_dates(text):
    """
    Извлекает все даты и диапазоны из текста (для страховки, если GPT пропустит).
    Возвращает список, например: ['Jan 2023 – Apr 2024', '2021', '2019 – Present'].
    """
    date_patterns = [
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*\s*\d{4}",
        r"\b(20\d{2}|19\d{2})\s*[-–]\s*(20\d{2}|present|jetzt|aktuell)\b",
        r"\b(20\d{2}|19\d{2})\b",
    ]
    found = []
    for pat in date_patterns:
        found.extend(re.findall(pat, text, flags=re.IGNORECASE))
    # нормализуем результат
    flat = []
    for f in found:
        if isinstance(f, tuple):
            flat.append(" – ".join([x for x in f if x]))
        else:
            flat.append(f)
    return list(dict.fromkeys(flat))  # уникальные
