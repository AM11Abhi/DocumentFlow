import re

def parse_marksheet(text: str) -> dict:
    data = {}
    gpa_match = re.search(r'gpa[\s:]*([0-9]\.[0-9]+)', text.lower())
    if gpa_match:
        data['gpa'] = gpa_match.group(1)
        
    percentage_match = re.search(r'([0-9]{2,3}(?:\.[0-9]+)?)\s*%', text)
    if percentage_match:
        data['percentage'] = percentage_match.group(1)
        
    return data

def parse_income_certificate(text: str) -> dict:
    data = {}
    # Look for INR/Rs or basic numbers with commas
    amount_match = re.search(r'(?:rs|inr|rupees)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', text.lower())
    if amount_match:
        data['amount'] = amount_match.group(1)
    return data

def parse_identity(text: str) -> dict:
    data = {}
    dob_match = re.search(r'(?:dob|date of birth)[\s:]*([\d]{2,4}[-/][\d]{2}[-/][\d]{2,4})', text.lower())
    if dob_match:
        data['dob'] = dob_match.group(1)
    return data

def parse_resume(text: str) -> dict:
    data = {}
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        data['email'] = email_match.group(0)
    
    phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        data['phone'] = phone_match.group(0)
    return data

def extract_data(doc_type: str, text: str) -> dict:
    if doc_type == "MARKSHEET":
        return parse_marksheet(text)
    elif doc_type == "INCOME_CERTIFICATE":
        return parse_income_certificate(text)
    elif doc_type == "IDENTITY_DOCUMENT":
        return parse_identity(text)
    elif doc_type == "RESUME":
        return parse_resume(text)
    return {}
