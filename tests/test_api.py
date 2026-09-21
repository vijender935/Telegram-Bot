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
    assert client.post("/v1/keys", headers={"Authorization": "Bearer wrong"}).status_code == 401
