import pdfplumber

def extract_text_from_pdf(pdf_path, max_pages=None, max_chars=None):
    """
    Extrahiert Text aus einer PDF-Datei mit optionalen Begrenzungen für Seiten und Zeichen.
    
    :param pdf_path: Pfad zur PDF-Datei
    :param max_pages: maximale Anzahl an Seiten, die verarbeitet werden (Standard: alle)
    :param max_chars: maximale Anzahl an Zeichen, die zurückgegeben werden (Standard: alles)
    :return: extrahierter Text
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    text = text.strip()
    if max_chars:
        text = text[:max_chars]  # Text kürzen, um Tokens zu sparen

    return text


# 🔹 Testlauf
if __name__ == "__main__":
    text = extract_text_from_pdf("data_input/CV_Kunde_1.pdf", max_pages=1, max_chars=500)
    print("📄 Extrahierter Text aus PDF:\n")
    print(text)
