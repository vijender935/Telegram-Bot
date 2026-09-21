"""Versioned REST API for trusted external clients."""
from __future__ import annotations

import asyncio
from functools import wraps
from flask import Blueprint, current_app, jsonify, request
from bot.core.observability import metrics, request_id, log_event

api = Blueprint("api", __name__, url_prefix="/v1")

def _bearer() -> str:
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.lower().startswith("bearer ") else ""

def require_scope(scope: str):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            rid = request.headers.get("X-Request-ID") or request_id()
            request.request_id = rid
            principal = current_app.config["api_key_store"].authenticate(_bearer())
            if not principal:
                return jsonify({"error": {"code": "unauthorized", "message": "Valid API key required"}, "request_id": rid}), 401
            if scope not in principal.scopes:
                return jsonify({"error": {"code": "forbidden", "message": "API key lacks required scope"}, "request_id": rid}), 403
            request.principal = principal
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@api.get("/health")
def api_health():
    return jsonify({"status": "ok", "service": "telegram-bot-api"})

@api.post("/chat")
@require_scope("chat:write")
def chat():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": {"code": "invalid_request", "message": "message is required"}, "request_id": request.request_id}), 400
    client_user_id = str(payload.get("user_id") or request.principal.key_id)
    try:
        user_id = int(payload.get("telegram_user_id")) if payload.get("telegram_user_id") is not None else _stable_external_id(client_user_id)
    except (TypeError, ValueError):
        user_id = _stable_external_id(client_user_id)
    service = current_app.config.get("chat_service")
    loop = current_app.config.get("bot_loop")
    if not service or not loop:
        return jsonify({"error": {"code": "not_ready", "message": "chat service is not ready"}, "request_id": request.request_id}), 503
    with metrics.timer("api.chat"):
        future = asyncio.run_coroutine_threadsafe(service.reply(user_id, message), loop)
        try:
            answer = future.result(timeout=current_app.config["api_timeout_seconds"])
        except TimeoutError:
            future.cancel()
            return jsonify({"error": {"code": "timeout", "message": "AI request timed out"}, "request_id": request.request_id}), 504
        except Exception:
            future.cancel()
            current_app.logger.exception("api chat failed request_id=%s", request.request_id)
            return jsonify({"error": {"code": "internal_error", "message": "AI request failed"}, "request_id": request.request_id}), 500
    log_event("api_chat", request_id=request.request_id, key_id=request.principal.key_id)
    return jsonify({"request_id": request.request_id, "response": answer, "model": current_app.config["model_name"]})

def _stable_external_id(value: str) -> int:
    import hashlib
    raw = hashlib.sha256(value.encode()).digest()[:8]
    return int.from_bytes(raw, "big") & 0x7FFFFFFFFFFFFFFF

@api.get("/profile")
@require_scope("profile:read")
def profile():
    user_id = _stable_external_id(str(request.args.get("user_id") or request.principal.key_id))
    memory = current_app.config["memory"]
    return jsonify({"request_id": request.request_id, "profile": memory.get_profile(user_id)})

@api.get("/keys")
def list_keys():
    admin = current_app.config.get("admin_api_key", "")
    if not admin or not secrets_match(_bearer(), admin):
        return jsonify({"error": {"code": "unauthorized", "message": "Admin API key required"}}), 401
    return jsonify({"keys": current_app.config["api_key_store"].list_keys()})

@api.post("/keys")
def create_key():
    admin = current_app.config.get("admin_api_key", "")
    if not admin or not secrets_match(_bearer(), admin):
        return jsonify({"error": {"code": "unauthorized", "message": "Admin API key required"}}), 401
    payload = request.get_json(silent=True) or {}
    scopes = payload.get("scopes") or ["chat:write", "profile:read"]
    allowed = {"chat:write", "profile:read"}
    if not isinstance(scopes, list) or not set(scopes).issubset(allowed):
        return jsonify({"error": {"code": "invalid_scopes", "message": "Unsupported scope"}}), 400
    key_id, token = current_app.config["api_key_store"].create(str(payload.get("name") or "client"), scopes)
    return jsonify({"key_id": key_id, "api_key": token, "scopes": scopes}), 201

@api.delete("/keys/<key_id>")
def revoke_key(key_id: str):
    admin = current_app.config.get("admin_api_key", "")
    if not admin or not secrets_match(_bearer(), admin):
        return jsonify({"error": {"code": "unauthorized", "message": "Admin API key required"}}), 401
    return jsonify({"revoked": current_app.config["api_key_store"].revoke(key_id)})

def secrets_match(a: str, b: str) -> bool:
    import hmac
    return bool(a and b) and hmac.compare_digest(a, b)
