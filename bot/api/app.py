"""HTTP application factory and middleware."""
from __future__ import annotations

import time

from flask import Flask, jsonify, request
from telegram import Update

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

    @app.post("/telegram")
    def telegram_webhook():
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        expected = app.config.get("telegram_webhook_secret", "")
        if not expected or secret != expected:
            return jsonify({"error": {"code": "forbidden", "message": "Invalid webhook secret"}}), 403
        telegram_app = app.config.get("telegram_app")
        bot_loop = app.config.get("bot_loop")
        if not telegram_app or not bot_loop:
            return jsonify({"error": {"code": "not_ready", "message": "Telegram application is not ready"}}), 503
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": {"code": "invalid_json", "message": "JSON body required"}}), 400
        try:
            update = Update.de_json(payload, bot=telegram_app.bot)
            bot_loop.call_soon_threadsafe(telegram_app.update_queue.put_nowait, update)
            return "", 200
        except Exception:
            app.logger.exception("telegram webhook enqueue failed request_id=%s", request.request_id)
            return jsonify({"error": {"code": "enqueue_failed", "message": "Update could not be queued"}, "request_id": request.request_id}), 500

    @app.get("/health")
    def health():
        result = app.config["health_check"]()
        return jsonify(result)

    @app.get("/metrics")
    def metrics():
        return jsonify(app.config["metrics_snapshot"]())
    return app
