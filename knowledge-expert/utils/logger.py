import time
from utils.supabase_admin import supabase
from utils.cost_calculator import calculate_cost, calculate_emb_cost

def log_query(query, anon_id, request_id=None, session_id=None):
    try:
        supabase.table("interaction_logs").insert(
            {
                "query": query,
                "anon_id": str(anon_id),
                "request_id": request_id,
                "session_id": session_id
            },
            returning="minimal"
        ).execute()
    except Exception as e:
        print(f"[LOGGING] failed: {e}")

def update_interaction_response(request_id, answer, sources):
    try:
        supabase.table("interaction_logs").update({
            "answer": answer,
            "sources": sources
        }).eq("request_id", request_id).execute()
    except Exception as e:
        print(f"[LOGGING] update failed: {e}")

def log_feedback(request_id, rating, reason=None):
    try:
        supabase.table("response_feedback").insert({
            "request_id": request_id,
            "rating": rating,
            "reason": reason
        }, returning="minimal").execute()
    except Exception as e:
        print(f"[FEEDBACK] failed: {e}")
        raise

def log_index_usage(emb_model, embedding_tokens=0):
    try:
        emb_cost = calculate_emb_cost(emb_model, embedding_tokens)

        supabase.table("index_usage_logs").insert({
            "embedding_model": emb_model,
            "embedding_cost": emb_cost,
            "embedding_tokens": embedding_tokens,
        }, returning="minimal").execute()

    except Exception as e:
        print(f"[USAGE] failed: {e}")

def log_chat_usage(request_id, anon_id, emb_model, llm_model, embedding_tokens=0, llm_input_tokens=0, llm_output_tokens=0):
    try:
        total_tokens = embedding_tokens + llm_input_tokens + llm_output_tokens

        emb_cost, llm_cost, input_cost, output_cost = calculate_cost(
            emb_model, 
            llm_model, 
            embedding_tokens, 
            llm_input_tokens, 
            llm_output_tokens
        )
        total_cost = emb_cost + llm_cost

        supabase.table("chat_usage_logs").insert({
            "request_id": request_id,
            "anon_id": str(anon_id),
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "embedding_model": emb_model,
            "embedding_cost": emb_cost,
            "embedding_tokens": embedding_tokens,
            "llm_model": llm_model,
            "llm_total_cost": llm_cost,
            "llm_input_cost": input_cost,
            "llm_input_tokens": llm_input_tokens,
            "llm_output_cost": output_cost,
            "llm_output_tokens": llm_output_tokens
        }, returning="minimal").execute()

    except Exception as e:
        print(f"[USAGE] failed: {e}")

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