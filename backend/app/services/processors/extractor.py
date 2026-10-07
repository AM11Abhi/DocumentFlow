import pymupdf

def extract_text(file_path: str) -> str:
    """Extracts text from a document using PyMuPDF."""
    text = ""
    try:
        with pymupdf.open(file_path) as doc:
            for page in doc:
                text += page.get_text() + "\n"
    except Exception as e:
        # If extraction fails (e.g. image format not supporting text natively or corrupted file)
        # we return empty text, which will result in UNKNOWN document type.
        pass
    return text.strip()
