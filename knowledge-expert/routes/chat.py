import re
import time
import json
import uuid
from threading import Thread
from flask import Blueprint, request, jsonify, Response, stream_with_context

from rag.retriever import hybrid_retrieve
from rag.chain import generate_answer
from utils.extensions import limiter
from utils.anonymizer import anonymize_query
from utils.logger import log_query, update_interaction_response, log_feedback
from utils.injection_patterns import INJECTION_PATTERNS
from utils.permissions import get_allowed_categories
from session.manager import SessionManager
from session.contextualizer import contextualize_question

session_manager = SessionManager()

chat_bp = Blueprint("chat", __name__)

MAX_QUERY_LENGTH = 1000
SOURCE_FIELDS = {"citation", "page", "source", "category", "uploaded_at", "section_title", "version"}

def validate_query(question):
    if not isinstance(question, str):
        return "question must be a string"

    question = " ".join(question.split())

    if not question:
        return "question is required"

    if len(question) > MAX_QUERY_LENGTH:
        return f"question must not exceed {MAX_QUERY_LENGTH} characters"

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, question, re.IGNORECASE):
            return "invalid question"

    return None

def extract_citations(answer):
    return set(re.findall(r"\[(\d+)\]", answer))

def log_query_background(query, anon_id, request_id, session_id):
    return log_query(query, anon_id, request_id, session_id)

@chat_bp.route("/chat", methods=["POST"])
@limiter.limit("10 per minute")
def chat():
    request_id = uuid.uuid4().hex[:8]
    request_start = time.perf_counter()

    print("CONTENT TYPE:", request.content_type)
    print("RAW BODY:", request.get_data(as_text=True))
    print("JSON:", request.get_json(silent=True))

    data = request.get_json(silent=True)

    role = request.headers.get("X-User-Role")

    if data is None:
        return jsonify({"error": "invalid JSON"}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be an object"}), 400

    question = data.get("question")
    session_id = data.get("session_id")

    error = validate_query(question)
    if error:
        return jsonify({"error": error}), 400

    question = " ".join(question.split())

    session, is_new = session_manager.get_or_create(session_id)
    session_id = session["session_id"]

    if is_new:
        title = question[:40] + ("..." if len(question) > 40 else "")
        session_manager.set_title(session_id, title)

    history = session_manager.get_history(session_id, limit=10)

    safe_query = anonymize_query(question)
    anon_id = uuid.uuid4()

    if history:
        contextual_question = contextualize_question(safe_query, history)
    else:
        contextual_question = safe_query

    session_manager.add_message(session_id, "user", safe_query)

    print(f"\n[{session_id[:8]}] id={session_id} new={is_new}")
    print(f"[{session_id[:8]}] history={history}")
    print(f"[{session_id[:8]}] question={safe_query}")
    print(f"[{session_id[:8]}] contextual_question={contextual_question}")

    log_start = time.perf_counter()
    log_query_background(safe_query, anon_id, request_id, session_id)
    log_time = time.perf_counter() - log_start
    with open("log/log_time.txt", "a", encoding="utf-8") as f:
        f.write(f"[{request_id}] [LOGGING] total={log_time:.3f}s\n")

    try:
        documents, context = hybrid_retrieve(
            contextual_question, request_id, role, allowed_categories=get_allowed_categories(role)
        )
    except Exception as error:
        print(f"[CHAT] hybrid_retrieve failed: {type(error).__name__}: {error}")
        Thread(
            target=update_interaction_response,
            args=(request_id, "Request gagal diproses.", [], "failed"),
            daemon=True
        ).start()
        return jsonify({"error": "failed to process request"}), 500

    if not documents:
        answer = "Informasi tidak ditemukan dalam knowledge base. Silakan hubungi kontak kami."
        session_manager.add_message(session_id, "assistant", answer)
        Thread(target=update_interaction_response, args=(request_id, answer, [], "fallback"), daemon=True).start()
        return jsonify({
            "session_id": session_id,
            "request_id": request_id,
            "question": safe_query,
            "answer": answer,
            "context": "",
            "sources": [],
            "fallback": True
        })

    sources = []
    for i, document in enumerate(documents, 1):
        metadata = document.metadata.copy()
        metadata["citation"] = str(i)
        sources.append(metadata)

    def generate():
        yield f"data: {json.dumps({
            'type': 'metadata',
            'session_id': session_id,
            'request_id': request_id,
            'fallback': False
        }, ensure_ascii=False)}\n\n"

        llm_start = time.perf_counter()
        first_token_time = None
        full_answer = []

        try:
            stream = generate_answer(safe_query, context)

            for chunk in stream:
                content = chunk.content

                if not content:
                    continue

                if first_token_time is None:
                    first_token_time = time.perf_counter() - llm_start

                full_answer.append(content)

                yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"

        except Exception:
            Thread(
                target=update_interaction_response,
                args=(request_id, "Request gagal diproses.", [], "failed"),
                daemon=True
            ).start()

            yield f"data: {json.dumps({'type': 'error', 'content': 'Request gagal diproses.'}, ensure_ascii=False)}\n\n"
            return

        llm_time = time.perf_counter() - llm_start
        total_time = time.perf_counter() - request_start

        answer = "".join(full_answer)

        used = extract_citations(answer)
        used_sources = [
            source for source in sources
            if source["citation"] in used
        ]

        stored_sources = [
            {k: v for k, v in s.items() if k in SOURCE_FIELDS}
            for s in used_sources
        ]
        session_manager.add_message(session_id, "assistant", answer, stored_sources)

        Thread(target=update_interaction_response, args=(request_id, answer, used_sources, "completed"), daemon=True).start()

        ttft = (
            first_token_time
            if first_token_time is not None
            else 0
        )

        log = (
            f"[{request_id}] [LLM] "
            f"ttft={ttft:.3f}s | "
            f"total={llm_time:.3f}s | "
            f"[{request_id}] [REQUEST] "
            f"total={total_time:.3f}s\n\n"
        )

        with open("log/log_time.txt", "a", encoding="utf-8") as f:
            f.write(log)

        yield f"data: {json.dumps({
            'type': 'answer',
            'content': answer
        }, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({
            'type': 'sources',
            'sources': used_sources
        }, ensure_ascii=False)}\n\n"

        yield 'data: {"type":"done"}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@chat_bp.route("/feedback", methods=["POST"])
@limiter.limit("20 per minute")
def feedback():
    data = request.get_json(silent=True) or {}

    request_id = data.get("request_id")
    rating = data.get("rating")
    reason = data.get("reason")

    if not request_id or not isinstance(request_id, str):
        return jsonify({"error": "request_id is required"}), 400

    if rating not in {"up", "down"}:
        return jsonify({"error": "rating must be 'up' or 'down'"}), 400

    if reason is not None and not isinstance(reason, str):
        return jsonify({"error": "reason must be a string"}), 400

    try:
        log_feedback(request_id, rating, reason)
    except ValueError:
        return jsonify({"error": "request_id not found"}), 404
    except Exception:
        return jsonify({"error": "failed to record feedback"}), 500

    return jsonify({"message": "feedback recorded"}), 201

@chat_bp.route("/sessions", methods=["POST"])
def list_sessions():
    data = request.get_json(silent=True) or {}
    session_ids = data.get("session_ids")

    if not isinstance(session_ids, list):
        return jsonify({"error": "session_ids must be an array"}), 400

    sessions = session_manager.list_sessions(session_ids)
    return jsonify(sessions)

@chat_bp.route("/sessions/<session_id>", methods=["GET"])
def get_session_history(session_id):
    session = session_manager.store.get(session_id)

    if not session:
        return jsonify({"error": "session not found or expired"}), 404

    messages = session_manager.store.get_messages(session_id, limit=100)

    return jsonify({
        "session_id": session_id,
        "title": session.get("title"),
        "messages": messages
    })

@chat_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    try:
        deleted = session_manager.store.delete(session_id)

        if not deleted:
            return jsonify({"error": "session not found"}), 404

        return jsonify({"message": "session deleted"}), 200

    except Exception:
        return jsonify({"error": "failed to delete session"}), 500

@chat_bp.route("/sessions/search", methods=["GET"])
def search_sessions():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify({"error": "q is required"}), 400

    if len(query) > 200:
        return jsonify({"error": "q must not exceed 200 characters"}), 400

    results = session_manager.search_sessions(query, limit=20)
    return jsonify(results)

@chat_bp.route("/rate-limit-test", methods=["GET"])
@limiter.limit("10 per minute")
def rate_limit_test():
    return jsonify({"message": "ok"})