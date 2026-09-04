from utils.supabase_client import supabase

def delete_expired_logs():
    try:
        result = supabase.rpc("delete_expired_query_logs").execute()
        deleted = result.data or 0
        print(f"[RETENTION] deleted={deleted}")
        return deleted
    except Exception as e:
        print(f"[RETENTION] failed: {e}")
        return 0

if __name__ == "__main__":
    delete_expired_logs()