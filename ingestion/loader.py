from docling.document_converter import DocumentConverter, InputFormat

converter = DocumentConverter()

def load_markdown(pages):
    documents = []
    for page in pages:
        result = converter.convert_string(page["markdown"], format=InputFormat.MD)
        documents.append({"page": page["page"], "document": result.document})
    return documents

def load_document(file_path):
    result = converter.convert(file_path)
    return result.document