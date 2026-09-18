import uuid
from datetime import datetime, timezone
from utils.supabase_admin import supabase

class SupabaseSessionStore:
    def create(self, user_id=None, title=None):
        now = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())

        row = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "created_at": now.isoformat(),
            "last_activity_at": now.isoformat(),
        }

        supabase.table("sessions").insert(row).execute()
        return row

    def get(self, session_id):
        result = supabase.table("sessions").select("*").eq("session_id", session_id).limit(1).execute()

        if not result.data:
            return None

        session = result.data[0]

        return session

    def touch(self, session_id):
        session = self.get(session_id)

        if not session:
            return None

        now = datetime.now(timezone.utc)

        supabase.table("sessions").update({
            "last_activity_at": now.isoformat()
        }).eq("session_id", session_id).execute()

        session["last_activity_at"] = now.isoformat()
        return session

    def set_title(self, session_id, title):
        supabase.table("sessions").update({"title": title}).eq("session_id", session_id).execute()

    def add_message(self, session_id, role, content, sources=None):
        if not self.get(session_id):
            return False

        supabase.table("session_messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
            "sources": sources
        }).execute()

        return True

    def get_messages(self, session_id, limit=10):
        if not self.get(session_id):
            return []

        result = (
            supabase.table("session_messages")
            .select("role, content, sources, created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return list(reversed(result.data or []))

    def list_sessions(self, session_ids):
        """Ambil daftar session (untuk sidebar) berdasarkan list session_id dari localStorage client."""
        if not session_ids:
            return []

        result = (
            supabase.table("sessions")
            .select("session_id, title, created_at, last_activity_at")
            .in_("session_id", session_ids)
            .order("last_activity_at", desc=True)
            .execute()
        )

        return result.data or []

    def cleanup(self):
        return 0

    def delete(self, session_id):
        result = (
            supabase.table("sessions")
            .delete()
            .eq("session_id", session_id)
            .execute()
        )

        return len(result.data or []) > 0