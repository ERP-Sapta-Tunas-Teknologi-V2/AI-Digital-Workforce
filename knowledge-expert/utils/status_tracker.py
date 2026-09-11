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

    existing = supabase.table("document_status").select("version_status").eq("document_id", document_id).execute()
    if not existing.data:
        data["version_status"] = "active"  # hanya set saat row baru dibuat

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

def supersede_status(old_document_id: str, new_document_id: str):
    """Tandai versi lama sebagai superseded. Row lama TIDAK dihapus (histori tetap ada)."""

    supabase.table("document_status").update({
        "version_status": "superseded",
        "superseded_by": new_document_id,
        "superseded_at": datetime.now(timezone.utc).isoformat()
    }).eq("document_id", old_document_id).execute()

def get_active_version(category: str):
    """Ambil document_id versi aktif untuk kategori tertentu (khusus kategori yang hanya boleh 1 versi aktif, mis. pricelist)."""

    result = (
        supabase
        .table("document_status")
        .select("document_id, source")
        .eq("category", category)
        .eq("version_status", "active")
        .execute()
    )
    return result.data or []

def get_version_number(document_id: str) -> int:
    """Versi dihitung dari jumlah kali document_id ini menjadi superseded_by (pengganti versi sebelumnya) + 1."""

    result = (
        supabase
        .table("document_status")
        .select("document_id", count="exact")
        .eq("superseded_by", document_id)
        .execute()
    )
    previous_versions = result.count or 0
    return previous_versions + 1