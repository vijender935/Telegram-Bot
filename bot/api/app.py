"""HTTP application factory and middleware."""
from __future__ import annotations
import time
from flask import Flask, jsonify, request
from bot.api.routes import api
from bot.core.observability import request_id

def create_http_app():
    app = Flask(__name__)
    app.register_blueprint(api)
    app.config.update(JSON_SORT_KEYS=False)

    @app.before_request
    def before():
        request.request_id = request.headers.get("X-Request-ID") or request_id()
        request.started_at = time.perf_counter()

    @app.after_request
    def after(response):
        response.headers["X-Request-ID"] = getattr(request, "request_id", "unknown")
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": {"code": "not_found", "message": "Endpoint not found"}, "request_id": getattr(request, "request_id", "unknown")}), 404

    @app.errorhandler(405)
    def method_not_allowed(_):
        return jsonify({"error": {"code": "method_not_allowed", "message": "Method not allowed"}, "request_id": getattr(request, "request_id", "unknown")}), 405

    @app.errorhandler(Exception)
    def unhandled(exc):
        app.logger.exception("unhandled http error request_id=%s", getattr(request, "request_id", "unknown"))
        return jsonify({"error": {"code": "internal_error", "message": "Internal server error"}, "request_id": getattr(request, "request_id", "unknown")}), 500

    @app.get("/")
    def home():
        return jsonify({"service": "Telegram Bot", "status": "ok", "api": "/v1"})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "telegram-bot"})

    @app.get("/metrics")
    def metrics():
        return jsonify(app.config["metrics_snapshot"]())
    return app
