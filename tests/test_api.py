from pathlib import Path

from bot.api.auth import ApiKeyStore
from bot.api.app import create_http_app


def test_api_key_lifecycle(tmp_path: Path):
    store = ApiKeyStore(str(tmp_path / "api.db"))
    key_id, token = store.create("test", ["chat:write"])
    principal = store.authenticate(token)
    assert principal is not None
    assert principal.key_id == key_id
    assert "chat:write" in principal.scopes
    assert store.revoke(key_id)
    assert store.authenticate(token) is None


def test_http_health_and_auth(tmp_path: Path):
    app = create_http_app()
    app.config.update(
        api_key_store=ApiKeyStore(str(tmp_path / "api.db")),
        admin_api_key="admin-secret",
        metrics_snapshot=lambda: {"ok": True},
        health_check=lambda: {"status": "ok"},
    )
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.post("/v1/keys", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_ready_returns_503_when_degraded(tmp_path: Path):
    app = create_http_app()
    app.config.update(
        api_key_store=ApiKeyStore(str(tmp_path / "api.db")),
        admin_api_key="admin-secret",
        metrics_snapshot=lambda: {"ok": True},
        health_check=lambda: {"status": "degraded"},
    )
    client = app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503


def test_api_identity_is_scoped_to_api_key(tmp_path: Path):
    from bot.api.routes import _stable_external_id

    app = create_http_app()
    store = ApiKeyStore(str(tmp_path / "api.db"))
    _, token = store.create("client", ["profile:read"])
    memory = type("Memory", (), {"get_profile": lambda self, user_id: {"user_id": user_id}})()
    app.config.update(
        api_key_store=store,
        admin_api_key="admin-secret",
        api_rate_limiter=None,
        memory=memory,
        health_check=lambda: {"status": "ok"},
        metrics_snapshot=lambda: {"ok": True},
    )
    client = app.test_client()
    response = client.get(
        "/v1/profile?user_id=999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    expected_id = _stable_external_id(store.list_keys()[0]["key_id"])
    assert response.get_json()["profile"]["user_id"] == expected_id


def test_chat_service_sanitizes_media_tool_output():
    from bot.application.chat_service import ChatService

    result = ChatService._tool_result_for_model(
        "search_images",
        {"type": "image", "data": "a" * 100000},
    )
    assert "base64" not in result
    assert "100000" not in result
    assert "not available" in result


def test_chat_service_sanitizes_embedded_image_markup():
    from bot.application.chat_service import ChatService

    result = ChatService._tool_result_for_model(
        "custom_tool",
        "![image](data:image/png;base64," + "a" * 100000 + ")",
    )
    assert "data:image" not in result
    assert "not available" in result
