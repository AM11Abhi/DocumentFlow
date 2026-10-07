from app.services.processors.extractor import extract_text
from app.services.processors.detector import detect_document_type
from app.services.processors.parsers import extract_data

def process_document(file_path: str) -> dict:
    """
    Main entry point for document processing.
    """
    text = extract_text(file_path)
    detection = detect_document_type(text)
    doc_type = detection["document_type"]
    data = extract_data(doc_type, text)
    
    return {
        "document_type": doc_type,
        "detection_score": detection["detection_score"],
        "matched_signals": detection["matched_signals"],
        "extracted_text": text,
        "extracted_data": data
    }
