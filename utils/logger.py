from utils.supabase_admin import supabase

def log_query(query, anon_id, request_id, session_id):
    try:
        supabase.table("interaction_logs").insert({
            "query": query,
            "anon_id": str(anon_id),
            "request_id": request_id,
            "session_id": session_id,
            "status": "started"
        }, returning="minimal").execute()
        return True

    except Exception as e:
        print(f"[LOGGING] failed: {e}")
        return False

def update_interaction_response(request_id, answer, sources, status="completed"):
    try:
        result = supabase.table("interaction_logs").update({
            "answer": answer,
            "sources": sources,
            "status": status
        }).eq("request_id", request_id).execute()

        if not result.data:
            print(f"[LOGGING] update matched no row for request_id={request_id}")

    except Exception as e:
        print(f"[LOGGING] update failed: {e}")

def log_feedback(request_id, rating, reason=None):
    try:
        supabase.table("response_feedback").upsert({
            "request_id": request_id,
            "rating": rating,
            "reason": reason
        }, on_conflict="request_id").execute()

    except Exception as e:
        error_str = str(e)
        if "foreign key" in error_str.lower() or "23503" in error_str:
            raise ValueError("request_id not found")
        print(f"[FEEDBACK] failed: {e}")
        raise

def log_ingestion(document_id, category, filename, result, status, duration_seconds, total_chunks=0, parse_error=None):
    try:
        supabase.table("ingestion_logs").insert({
            "document_id": document_id,
            "category": category,
            "filename": filename,
            "total_chunks": total_chunks,
            "chunks_inserted": result.get("inserted", 0),
            "chunks_updated": result.get("updated", 0),
            "chunks_skipped": result.get("skipped", 0),
            "chunks_deleted": result.get("deleted", 0),
            "chunks_failed": result.get("failed", 0),
            "parse_error": parse_error,
            "status": status,
            "duration_seconds": duration_seconds
        }, returning="minimal").execute()

    except Exception as e:
        print(f"[INGESTION LOG] failed: {e}")