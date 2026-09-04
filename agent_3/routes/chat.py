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
from utils.logger import log_query, log_chat_usage
from session.manager import SessionManager
from session.contextualizer import contextualize_question
from utils.injection_patterns import INJECTION_PATTERNS
from config.settings import OLLAMA_LLM

session_manager = SessionManager()

chat_bp = Blueprint("chat", __name__)

MAX_QUERY_LENGTH = 1000

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

def log_query_background(query, anon_id):
    try:
        return log_query(query, anon_id)
    except Exception as e:
        print(f"[LOGGING] failed: {e}")

def log_usage_background(request_id, anon_id, embedding_model, embedding_tokens, llm_input_tokens, llm_output_tokens):
    try:
        log_chat_usage(
            request_id=request_id,
            anon_id=anon_id,
            emb_model=embedding_model,
            llm_model=OLLAMA_LLM,
            embedding_tokens=embedding_tokens,
            llm_input_tokens=llm_input_tokens,
            llm_output_tokens=llm_output_tokens
        )
    except Exception as e:
        print(f"[USAGE] failed: {e}")

@chat_bp.route("/chat", methods=["POST"])
@limiter.limit("10 per minute")
def chat():
    request_id = uuid.uuid4().hex[:8]
    request_start = time.perf_counter()

    print("CONTENT TYPE:", request.content_type)
    print("RAW BODY:", request.get_data(as_text=True))
    print("JSON:", request.get_json(silent=True))

    data = request.get_json(silent=True)

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

    usage = {
        "embedding_tokens": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0
    }

    log_start = time.perf_counter()
    Thread(target=log_query_background, args=(safe_query, anon_id), daemon=True).start()
    log_time = time.perf_counter() - log_start
    with open("log/log_time.txt", "a", encoding="utf-8") as f:
        f.write(f"[{request_id}] [LOGGING] total={log_time:.3f}s\n")

    documents, context, embedding_tokens, embedding_model = hybrid_retrieve(contextual_question, request_id)
    usage["embedding_tokens"] = embedding_tokens
    usage["embedding_model"] = embedding_model

    if not documents:
        answer = "Informasi tidak ditemukan dalam knowledge base. Silakan hubungi kontak kami."
        session_manager.add_message(session_id, "assistant", answer)
        return jsonify({
            "session_id": session_id,
            "question": safe_query,
            "answer": answer,
            "context": "",
            "sources": [],
            "fallback": True
        })

    sources = [document.metadata for document in documents]

# Non-Stream
#     answer = generate_answer(safe_query, context)
#     return jsonify({
#         "question": safe_query,
#         "answer": answer,
#         "context": context,
#         "sources": sources,
#         "fallback": False
#     })

    def generate():
        yield f"data: {json.dumps({
            'type': 'metadata',
            'session_id': session_id,
            'sources': sources,
            'fallback': False
        }, ensure_ascii=False)}\n\n"

        llm_start = time.perf_counter()
        first_token_time = None
        full_answer = []

        stream = generate_answer(safe_query, context)

        for chunk in stream:
            metadata = getattr(chunk, "usage_metadata", None)

            if metadata:
                usage["llm_input_tokens"] = metadata.get("input_tokens", 0)
                usage["llm_output_tokens"] = metadata.get("output_tokens", 0)

            # Ollama
            content = chunk.content

            # API
            # if not chunk.choices:
            #     continue
            # content = getattr(chunk.choices[0].delta, "content", None)

            if not content:
                continue

            if first_token_time is None:
                first_token_time = time.perf_counter() - llm_start

            full_answer.append(content)

            yield f"data: {json.dumps({'type': 'token', 'content': content}, ensure_ascii=False)}\n\n"

        llm_time = time.perf_counter() - llm_start
        total_time = time.perf_counter() - request_start

        answer = "".join(full_answer)

        session_manager.add_message(session_id, "assistant", answer)

        Thread(
            target=log_usage_background,
            args=(
                request_id,
                anon_id,
                usage["embedding_model"],
                usage["embedding_tokens"],
                usage["llm_input_tokens"],
                usage["llm_output_tokens"]
            ),
            daemon=True
        ).start()

        ttft = (
            first_token_time
            if first_token_time is not None
            else 0
        )

        log = (
            f"[{request_id}] [LLM] "
            f"ttft={ttft:.3f}s | "
            f"total={llm_time:.3f}s | "
            f"input_tokens="
            f"{usage['llm_input_tokens']} | "
            f"output_tokens="
            f"{usage['llm_output_tokens']}\n"
            f"[{request_id}] [REQUEST] "
            f"total={total_time:.3f}s\n\n"
        )

        with open("log/log_time.txt", "a", encoding="utf-8") as f:
            f.write(log)

        yield f"data: {json.dumps({
            'type': 'answer',
            'content': answer
        }, ensure_ascii=False)}\n\n"

        yield 'data: {"type":"done"}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@chat_bp.route("/rate-limit-test", methods=["GET"])
@limiter.limit("10 per minute")
def rate_limit_test():
    return jsonify({"message": "ok"})