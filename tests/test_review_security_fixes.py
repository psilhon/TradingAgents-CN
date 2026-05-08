import inspect

import pytest
from fastapi.params import Depends

from app.routers import config, multi_source_sync, sync, websocket_notifications


@pytest.mark.unit
def test_secret_meta_does_not_include_secret_value():
    secret = "sk-test-secret-value"

    meta = config._secret_meta(secret)

    assert "present=True" in meta
    assert "length=20" in meta
    assert secret not in meta


@pytest.mark.unit
def test_sync_mutation_endpoints_require_authenticated_user_dependency():
    sync_params = inspect.signature(sync.run_stock_basics_sync).parameters
    multi_run_params = inspect.signature(multi_source_sync.run_stock_basics_sync).parameters
    clear_cache_params = inspect.signature(multi_source_sync.clear_sync_cache).parameters

    assert isinstance(sync_params["current_user"].default, Depends)
    assert isinstance(multi_run_params["current_user"].default, Depends)
    assert isinstance(clear_cache_params["current_user"].default, Depends)


@pytest.mark.unit
def test_sync_mutation_endpoints_reject_non_admin_users():
    with pytest.raises(Exception) as sync_exc:
        sync._require_admin({"is_admin": False})
    with pytest.raises(Exception) as multi_exc:
        multi_source_sync._require_admin({"is_admin": False})

    assert getattr(sync_exc.value, "status_code", None) == 403
    assert getattr(multi_exc.value, "status_code", None) == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_progress_without_user_id_is_not_broadcast(monkeypatch):
    calls = []

    class FakeManager:
        async def send_personal_message(self, message, user_id):
            calls.append(("personal", user_id, message))

        async def broadcast(self, message):
            calls.append(("broadcast", message))

    monkeypatch.setattr(websocket_notifications, "manager", FakeManager())

    await websocket_notifications.send_task_progress_via_websocket("task-1", {"progress": 10})

    assert calls == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_task_progress_with_user_id_sends_personal_message(monkeypatch):
    calls = []

    class FakeManager:
        async def send_personal_message(self, message, user_id):
            calls.append(("personal", user_id, message))

        async def broadcast(self, message):
            calls.append(("broadcast", message))

    monkeypatch.setattr(websocket_notifications, "manager", FakeManager())

    await websocket_notifications.send_task_progress_via_websocket(
        "task-1",
        {"user_id": "alice", "progress": 10},
    )

    assert calls == [
        (
            "personal",
            "alice",
            {"type": "progress", "data": {"user_id": "alice", "progress": 10}},
        )
    ]
