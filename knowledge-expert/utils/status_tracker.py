from utils.supabase_admin import supabase
from datetime import datetime, timezone

def set_status(document_id: str, source: str, category: str, status: str, detail: str = None):
    (
        supabase
        .table("document_status")
        .upsert({
            "document_id": document_id,
            "source": source,
            "category": category,
            "status": status,
            "detail": detail,
            "last_ingested_at": datetime.now(timezone.utc).isoformat()
        })
        .execute()
    )