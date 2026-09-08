from utils.supabase_admin import supabase
from datetime import datetime, timezone

def set_status(document_id, source, category, status, detail=None):
    data = {
        "document_id": document_id,
        "source": source,
        "category": category,
        "status": status,
        "detail": detail
    }

    if status in {"success", "failed"}:
        data["last_ingested_at"] = datetime.now(timezone.utc).isoformat()

    supabase.table("document_status").upsert(data).execute()

def get_all_statuses():
    result = (
        supabase
        .table("document_status")
        .select("document_id, status, last_ingested_at")
        .execute()
    )
    return result.data or []

def delete_status(document_id: str):
    (
        supabase
        .table("document_status")
        .delete()
        .eq("document_id", document_id)
        .execute()
    )