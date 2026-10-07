import re

def anonymize_query(query):
    query = re.sub(r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]', query)
    query = re.sub(r'(?<!\d)(?:\+62|62|0)8\d{8,12}(?!\d)', '[PHONE]', query)
    query = re.sub(r'(?i)\b(?:nama saya|saya bernama)\s+[A-Za-zÀ-ÿ]+(?:\s+[A-Za-zÀ-ÿ]+)*', '[NAME]', query)
    return query.strip()