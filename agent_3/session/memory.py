import uuid
from datetime import datetime, timedelta, timezone

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_TIMEOUT = timedelta(hours=24)

class MemorySessionStore:
    def __init__(self):
        self.sessions = {}
        self.messages = {}

    def create(self, user_id=None):
        now = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())

        self.sessions[session_id] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "last_activity_at": now,
            "expires_at": now + IDLE_TIMEOUT,
            "absolute_expires_at": now + ABSOLUTE_TIMEOUT,
        }
        self.messages[session_id] = []

        return self.sessions[session_id]

    def get(self, session_id):
        session = self.sessions.get(session_id)

        if not session:
            return None

        now = datetime.now(timezone.utc)

        if now >= session["expires_at"] or now >= session["absolute_expires_at"]:
            return None

        return session

    def touch(self, session_id):
        session = self.get(session_id)

        if not session:
            return None

        now = datetime.now(timezone.utc)
        session["last_activity_at"] = now
        session["expires_at"] = min(
            now + IDLE_TIMEOUT,
            session["absolute_expires_at"]
        )

        return session

    def add_message(self, session_id, role, content):
        if not self.get(session_id):
            return False

        self.messages[session_id].append({
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc),
        })

        return True

    def get_messages(self, session_id, limit=10):
        if not self.get(session_id):
            return []

        return self.messages.get(session_id, [])[-limit:]

    def cleanup(self):
        expired = []

        for session_id in list(self.sessions):
            if not self.get(session_id):
                expired.append(session_id)

        for session_id in expired:
            self.sessions.pop(session_id, None)
            self.messages.pop(session_id, None)

        return len(expired)