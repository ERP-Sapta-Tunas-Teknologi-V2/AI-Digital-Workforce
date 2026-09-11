import re
import hashlib
import io
import pymupdf
from datetime import datetime, timezone
from docx import Document
from pathlib import Path
from utils.supabase_admin import supabase

CONFIDENTIAL_PATTERNS = [
    r"\brahasia\s+perusahaan\b",
    r"\bconfidential\b",
    r"\binternal\s+only\b",
    r"\bstrictly\s+confidential\b",
    r"\bjangan\s+disebarluaskan\b",
    r"\bdilarang\s+didistribusikan\b",
]

STALE_MARKERS = [
    r"\bdraft\b",
    r"\bdeprecated\b",
    r"\bkadaluarsa\b",
    r"\bexpired\b",
    r"\btidak\s+berlaku\s+lagi\b",
]

def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def extract_text_sample(filename: str, file_bytes: bytes, max_chars: int = 5000) -> str:
    """
    Ekstraksi teks ringan untuk screening.
    Tidak melakukan LibreOffice atau markdown conversion.
    """
    ext = Path(filename).suffix.lower()

    try:
        if ext == ".pdf":
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text[:max_chars]

        if ext == ".docx":
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join(
                p.text for p in doc.paragraphs if p.text.strip()
            )
            return text[:max_chars]

    except Exception as e:
        print(f"[SCREENING] text extraction failed: {e}")

    return ""

def find_duplicate(file_hash: str, exclude_document_id: str = None):
    query = supabase.table("document_flags").select("document_id").eq("file_hash", file_hash)
    result = query.execute()
    for row in result.data or []:
        if row["document_id"] != exclude_document_id:
            return row["document_id"]
    return None

def scan_text_for_flags(text: str):
    flags = []
    lowered = text.lower()

    for pattern in CONFIDENTIAL_PATTERNS:
        if re.search(pattern, lowered):
            flags.append(("confidential", f"matched pattern: {pattern}"))
            break

    for pattern in STALE_MARKERS:
        if re.search(pattern, lowered):
            flags.append(("stale", f"matched pattern: {pattern}"))
            break

    return flags

def record_flag(document_id, flag_type, detail=None, duplicate_of=None, file_hash=None):
    try:
        supabase.table("document_flags").upsert({
            "document_id": document_id,
            "flag_type": flag_type,
            "detail": detail,
            "duplicate_of": duplicate_of,
            "file_hash": file_hash,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception as e:
        print(f"[SCREENING] failed to record flag: {e}")

def clear_flags(document_id):
    try:
        supabase.table("document_flags").delete().eq("document_id", document_id).execute()
    except Exception as e:
        print(f"[SCREENING] failed to clear flags: {e}")

def screen_document(document_id: str, file_bytes: bytes, text_sample: str = ""):
    """
    Return (should_block, flags) — should_block=True berarti dokumen TIDAK
    boleh diproses otomatis (perlu review), flags berisi semua temuan.
    """
    clear_flags(document_id)

    file_hash = compute_file_hash(file_bytes)
    flags_found = []

    duplicate_id = find_duplicate(file_hash, exclude_document_id=document_id)
    if duplicate_id:
        record_flag(document_id, "duplicate", f"identical to {duplicate_id}", duplicate_of=duplicate_id, file_hash=file_hash)
        flags_found.append(("duplicate", duplicate_id))

    if text_sample:
        for flag_type, detail in scan_text_for_flags(text_sample):
            record_flag(document_id, flag_type, detail, file_hash=file_hash)
            flags_found.append((flag_type, detail))

    if not flags_found:
        record_flag_none = None  # tidak ada flag, tapi tetap simpan hash untuk cek duplikat berikutnya
        record_flag(document_id, "clean", "no issues detected", file_hash=file_hash)

    should_block = any(f[0] in {"duplicate", "confidential"} for f in flags_found)
    return should_block, flags_found