import fitz  # PyMuPDF
import re


def extract_text_by_page(pdf_path):
    """
    Extracts text page-by-page from a PDF using PyMuPDF.
    Returns list of strings (one per page).
    """
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text().strip() for page in doc]
    doc.close()
    return pages_text


def clean_text(text):
    """
    Normalize and tag known sections like [DOMAINS], [EDUCATION], etc.
    """
    # Remove indexes like [1], (2)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\(\d+\)", "", text)

    # Remove excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    # Add section markers without removing original titles
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

    # Add closing tags for cleaner block extraction
    text = re.sub(r"\[DOMAINS\](.*?)\n(?=\[|\Z)", r"[DOMAINS]\1[/DOMAINS]\n", text, flags=re.DOTALL)
    text = re.sub(r"\[SKILLS\](.*?)\n(?=\[|\Z)", r"[SKILLS]\1[/SKILLS]\n", text, flags=re.DOTALL)
    text = re.sub(r"\[LANGUAGES\](.*?)\n(?=\[|\Z)", r"[LANGUAGES]\1[/LANGUAGES]\n", text, flags=re.DOTALL)
    text = re.sub(r"\[EDUCATION\](.*?)\n(?=\[|\Z)", r"[EDUCATION]\1[/EDUCATION]\n", text, flags=re.DOTALL)
    text = re.sub(r"\[PROJECTS\](.*?)\n(?=\[|\Z)", r"[PROJECTS]\1[/PROJECTS]\n", text, flags=re.DOTALL)
    text = re.sub(r"\[PROFILE_SUMMARY\](.*?)\n(?=\[|\Z)", r"[PROFILE_SUMMARY]\1[/PROFILE_SUMMARY]\n", text, flags=re.DOTALL)

    return text.strip()

def clean_responsibilities(responsibilities, max_words=12):
    """
    Kürzt und bereinigt die 'responsibilities'-Liste.
    Lange Sätze werden abgeschnitten, aber so,
    dass der Sinn nicht komplett verloren geht.
    """
    cleaned = []
    for resp in responsibilities:
        # убираем пробелы и точки в конце
        resp = resp.strip().rstrip(".;:")

        # делим на слова
        words = resp.split()

        if len(words) > max_words:
            # берём первые max_words слов и добавляем "..."
            short = " ".join(words[:max_words]) + "..."
            cleaned.append(short)
        else:
            cleaned.append(resp)

    return cleaned


def extract_domains_from_text(text):
    """
    Extract exact values inside [DOMAINS] ... [/DOMAINS]
    """
    match = re.search(r"\[DOMAINS\](.*?)\[/DOMAINS\]", text, re.DOTALL)
    if not match:
        return []
    lines = match.group(1).split("\n")
    return [line.strip() for line in lines if line.strip()]


