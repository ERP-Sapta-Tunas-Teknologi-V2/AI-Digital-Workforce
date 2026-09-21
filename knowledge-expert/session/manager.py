from .memory import SupabaseSessionStore

class SessionManager:
    def __init__(self, store=None):
        self.store = store or SupabaseSessionStore()

    def get_or_create(self, session_id=None, user_id=None, title=None):
        if session_id:
            session = self.store.get(session_id)

            if session:
                self.store.touch(session_id)
                return session, False

        return self.store.create(user_id, title), True

    def add_message(self, session_id, role, content, sources=None):
        return self.store.add_message(session_id, role, content, sources)

    def get_history(self, session_id, limit=10):
        return self.store.get_messages(session_id, limit)

    def set_title(self, session_id, title):
        return self.store.set_title(session_id, title)

    def list_sessions(self, session_ids):
        return self.store.list_sessions(session_ids)

    def list_all_sessions(self):
        return self.store.list_all_sessions()

    def cleanup(self):
        return self.store.cleanup()

    def delete_session(self, session_id):
        return self.store.delete(session_id)

    def search_sessions(self, query, user_id=None, limit=20):
        return self.store.search_messages(query, user_id=user_id, limit=limit)