from .memory import MemorySessionStore

class SessionManager:
    def __init__(self, store=None):
        self.store = store or MemorySessionStore()

    def get_or_create(self, session_id=None, user_id=None):
        if session_id:
            session = self.store.get(session_id)

            if session:
                self.store.touch(session_id)
                return session, False

        return self.store.create(user_id), True

    def add_message(self, session_id, role, content):
        return self.store.add_message(session_id, role, content)

    def get_history(self, session_id, limit=10):
        return self.store.get_messages(session_id, limit)

    def cleanup(self):
        return self.store.cleanup()