from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
import redis
import requests
import time

from utils.extensions import limiter
from utils.minio_client import ensure_bucket, client
from routes.chat import chat_bp
from routes.analytics import analytics_bp
from routes.admin import admin_bp
from config import OLLAMA_BASE_URL

ALLOWED_ORIGINS = ["http://localhost:5173"]

REDIS_HOST = "localhost"
REDIS_PORT = 6379

def check_services():
    print("[CHECK] Checking services...")

    # MinIO
    try:
        client.list_buckets()
        print("[OK] MinIO")
    except Exception as e:
        print(f"[ERROR] MinIO: {e}")
        return False

    # Redis
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
        r.ping()
        print("[OK] Redis")
    except Exception as e:
        print(f"[ERROR] Redis: {e}")
        return False

    # Ollama
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        response.raise_for_status()
        print("[OK] Ollama")
    except Exception as e:
        print(f"[ERROR] Ollama: {e}")
        return False

    print("[CHECK] All services are running")
    return True

def create_app():
    while not check_services():
        print("[RETRY] Services belum siap. Coba lagi dalam 5 detik...", flush=True)
        time.sleep(5)

    app = Flask(__name__)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

    ensure_bucket()
    print(client.list_buckets())

    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    @app.route("/")
    def index():
        return send_from_directory("static", "chat.html")

    @app.route("/dashboard")
    def dashboard():
        return send_from_directory("static", "dashboard.html")

    @app.errorhandler(429)
    def handle_rate_limit(e):
        return jsonify({
            "error": "rate limit exceeded",
            "message": "Terlalu banyak request. Silakan coba lagi nanti."
        }), 429

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)