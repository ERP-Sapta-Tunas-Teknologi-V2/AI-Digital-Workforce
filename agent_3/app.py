from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from utils.extensions import limiter
from routes.chat import chat_bp
from routes.analytics import analytics_bp

ALLOWED_ORIGINS = ["https://saptatunas.com"]

def create_app():
    app = Flask(__name__)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return send_from_directory("static", "index.html")

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