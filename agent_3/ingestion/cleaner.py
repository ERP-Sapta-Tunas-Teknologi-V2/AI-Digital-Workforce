from docx2pdf import convert
import pymupdf
import pymupdf4llm
import re
import tempfile
from pathlib import Path

def docx_to_pdf(docx_path, pdf_path):
    print("Converting .docx to .pdf")
    convert(docx_path, pdf_path)

def pdf_to_md(pdf_path):
    print("Converting .pdf to .md")
    pdf = pymupdf.open(pdf_path)
    pages = []
    for page_number in range(len(pdf)):
        markdown = pymupdf4llm.to_markdown(pdf, pages=[page_number])
        pages.append({"page": page_number + 1, "markdown": markdown})
    pdf.close()
    return pages

def clean_md(markdown):
    markdown = markdown.replace("**", "")  # Remove bold
    markdown = re.sub(r"^# (?!#)", "## ", markdown, flags=re.MULTILINE)  # h1 (#) to h2 (##)
    markdown = re.sub(re.compile("<.*?>"), " ", markdown)  # Remove html tags
    markdown = markdown.replace("`", "")  # Remove `
    return markdown

def preprocessing(path, document_id):
    if path.suffix.lower() == ".docx":
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / f"{document_id}.pdf"
            docx_to_pdf(path, pdf_path)
            pages = pdf_to_md(pdf_path)

    elif path.suffix.lower() == ".pdf":
        pages = pdf_to_md(pdf_path)
        
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")

    print("Cleaning .md")
    for page in pages:
        page["markdown"] = clean_md(page["markdown"])

    return pages