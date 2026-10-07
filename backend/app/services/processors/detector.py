def detect_document_type(text: str) -> dict:
    """
    Rule-based document type detection.
    Values: MARKSHEET, INCOME_CERTIFICATE, IDENTITY_DOCUMENT, RESUME, UNKNOWN
    """
    if not text:
        return {"document_type": "UNKNOWN", "detection_score": 0, "matched_signals": []}
        
    text_lower = text.lower()
    
    signals = {
        "MARKSHEET": ["university", "transcript", "grades", "gpa", "semester", "marks", "board", "course"],
        "INCOME_CERTIFICATE": ["income", "revenue", "salary", "certificate", "tax", "annual", "financial"],
        "IDENTITY_DOCUMENT": ["passport", "id", "license", "citizen", "dob", "identity", "government", "national"],
        "RESUME": ["experience", "education", "skills", "resume", "cv", "profile", "projects"],
    }
    
    scores = {doc_type: 0 for doc_type in signals}
    matched = {doc_type: [] for doc_type in signals}
    
    for doc_type, keywords in signals.items():
        for keyword in keywords:
            if keyword in text_lower:
                scores[doc_type] += 1
                matched[doc_type].append(keyword)
                
    max_score = 0
    detected_type = "UNKNOWN"
    
    for doc_type, score in scores.items():
        if score > max_score:
            max_score = score
            detected_type = doc_type
            
    return {
        "document_type": detected_type,
        "detection_score": max_score,
        "matched_signals": matched.get(detected_type, [])
    }
