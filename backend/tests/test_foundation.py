from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent import ToolGateway
from app.config import Settings
from app.db import FitnessObject, ObjectRevision, Outbox, Receipt, User
from app.domain import DomainError


def submit(client, auth, operations, operation_id=None):
    operation_id = operation_id or str(uuid4())
    return client.post("/api/v1/agent-actions/apply", headers={**auth, "Idempotency-Key": operation_id},
                       json={"operation_id": operation_id, "operations": operations})


def create(text="今天练腿，很累", kind="activity"):
    return {"action": "create", "kind": kind, "payload": {"text": text, "activity_status": "reported"}}


def test_free_record_replay_and_custom_fields(client, auth, app):
    operation_id = str(uuid4())
    operation = create()
    operation["payload"]["我的感受"] = {"关键词": ["很累", "满意"], "刻度": "自定义"}
    first = submit(client, auth, [operation], operation_id)
    assert first.status_code == 200
    saved = first.json()["data"]
    assert saved["objects"][0]["payload"] == operation["payload"]
    assert submit(client, auth, [operation], operation_id).json()["data"] == saved
    assert submit(client, auth, [create("另一条")], operation_id).status_code == 409
    with app.state.sessions() as db:
        for model in (FitnessObject, ObjectRevision, Outbox, Receipt):
            assert db.scalar(select(func.count()).select_from(model)) == 1


def test_supplement_version_undo_and_no_double_count(client, auth):
    obj = submit(client, auth, [create()]).json()["data"]["objects"][0]
    change = {"action": "replace", "object_id": obj["id"], "expected_version": 1,
              "payload": {**obj["payload"], "感受补充": "不是疼痛"}}
    response = submit(client, auth, [change])
    assert response.json()["data"]["training_revision"] == 2
    assert submit(client, auth, [change]).status_code == 409
    undo = submit(client, auth, [{"action": "undo", "object_id": obj["id"],
                                 "expected_version": 2, "restore_version": 1}])
    assert undo.json()["data"]["objects"][0]["version"] == 3
    assert undo.json()["data"]["objects"][0]["payload"] == obj["payload"]
    assert len(client.get("/api/v1/objects", headers=auth).json()["data"]["items"]) == 1
    assert len(client.get(f'/api/v1/objects/{obj["id"]}/revisions', headers=auth).json()["data"]["items"]) == 3


def test_atomic_group_rollback(client, auth):
    result = submit(client, auth, [create(), {"action": "replace", "object_id": str(uuid4()),
                                            "expected_version": 1, "payload": {}}])
    assert result.status_code == 404
    assert client.get("/api/v1/objects", headers=auth).json()["data"]["items"] == []
    assert client.get("/api/v1/me", headers=auth).json()["data"]["training_revision"] == 0


def test_cross_user_and_unknown_kind(client, auth):
    obj = submit(client, auth, [create(kind="我的运动心情")]).json()["data"]["objects"][0]
    other = client.post("/api/v1/auth/dev-session").json()["data"]
    other_auth = {"Authorization": "Bearer " + other["access_token"]}
    assert client.get("/api/v1/objects", headers=other_auth).json()["data"]["items"] == []
    assert client.get(f'/api/v1/objects/{obj["id"]}/revisions', headers=other_auth).status_code == 404
    assert submit(client, other_auth, [{"action": "replace", "object_id": obj["id"],
                                       "expected_version": 1, "payload": {}}]).status_code == 404
    assert client.get("/api/v1/objects").status_code == 401
    assert client.get("/api/v1/objects", headers={"Authorization": "Bearer fake"}).status_code == 401


def test_concurrent_retries_are_one_write(client, auth, app):
    op = str(uuid4())
    def send(_):
        with TestClient(app) as separate:
            return submit(separate, auth, [create()], op)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(send, range(8)))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()["data"]["objects"][0]["id"] for r in results}) == 1
    assert client.get("/api/v1/me", headers=auth).json()["data"]["training_revision"] == 1


def test_concurrent_version_updates_one_winner(client, auth, app):
    obj = submit(client, auth, [create()]).json()["data"]["objects"][0]
    def send(index):
        with TestClient(app) as separate:
            return submit(separate, auth, [{"action": "replace", "object_id": obj["id"],
                                            "expected_version": 1, "payload": {"text": str(index)}}])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]


def test_agent_record_survives_provider_failure_and_replay(client, auth, app):
    class BrokenPlanner:
        def complete(self, messages, tools):
            raise DomainError("MODEL_UNAVAILABLE", "暂不可用", 503)
    app.state.planner = BrokenPlanner()
    conversation = client.post("/api/v1/conversations", headers=auth).json()["data"]["id"]
    op = str(uuid4())
    body = {"operation_id": op, "text": "今天打球了，没有统计时间", "intent": "record"}
    path = f"/api/v1/conversations/{conversation}/messages"
    response = client.post(path, headers={**auth, "Idempotency-Key": op}, json=body)
    saved = response.json()["data"]
    assert saved["status"] == "partial" and len(saved["receipts"]) == 1
    assert client.post(path, headers={**auth, "Idempotency-Key": op}, json=body).json()["data"] == saved
    assert len(client.get(path, headers=auth).json()["data"]["items"]) == 1
    assert len(client.get("/api/v1/objects", headers=auth).json()["data"]["items"]) == 1


def test_agent_tool_order_and_authority(client, auth, app):
    class ToolPlanner:
        def complete(self, messages, tools):
            responses = [m for m in messages if m["role"] == "tool"]
            names = ["read_context", "apply_changes", "calculate_summary", "apply_changes"]
            if len(responses) == len(names):
                return {"role": "assistant", "content": "已记录。"}
            name = names[len(responses)]
            arguments = "{}"
            if name == "apply_changes":
                arguments = '{"operations":[{"action":"create","kind":"activity","payload":{"text":"模型改写的内容","activity_status":"finished","duration_minutes":90}}]}'
            return {"role": "assistant", "tool_calls": [{"id": str(uuid4()), "type": "function",
                     "function": {"name": name, "arguments": arguments}}]}
    app.state.planner = ToolPlanner()
    conversation = client.post("/api/v1/conversations", headers=auth).json()["data"]["id"]
    op = str(uuid4())
    result = client.post(f"/api/v1/conversations/{conversation}/messages",
                         headers={**auth, "Idempotency-Key": op},
                         json={"operation_id": op, "text": "今天爬山", "intent": "record"})
    assert result.status_code == 200
    assert len(result.json()["data"]["receipts"]) == 1
    assert result.json()["data"]["receipts"][0]["objects"][0]["payload"] == {
        "text": "今天爬山", "activity_status": "reported",
    }
    assert len(client.get("/api/v1/objects", headers=auth).json()["data"]["items"]) == 1
    gateway = ToolGateway(app.state.sessions, "unused", str(uuid4()), "测试", "chat")
    with pytest.raises(DomainError, match="当前任务没有此能力"):
        gateway.invoke("apply_changes", {})


def test_agent_current_task_can_create_flexible_plan_once(client, auth, app):
    class PlanPlanner:
        def complete(self, messages, tools):
            calls = [message for message in messages if message["role"] == "tool"]
            if not calls:
                return {"role": "assistant", "tool_calls": [{"id": str(uuid4()), "type": "function",
                    "function": {"name": "apply_changes", "arguments":
                        '{"operations":[{"action":"create","kind":"plan","payload":'
                        '{"title":"慢慢建立习惯","intent":"每次先决定","custom_preferences":{"无固定日期":true},'
                        '"nodes":[{"id":"stable-a","text":"选择今天舒服的活动","status":"unstarted"}]}}]}'}}]}
            return {"role": "assistant", "content": "已整理一份弹性草案。"}
    app.state.planner = PlanPlanner()
    conversation = client.post("/api/v1/conversations", headers=auth).json()["data"]["id"]
    op = str(uuid4())
    response = client.post(f"/api/v1/conversations/{conversation}/messages",
        headers={**auth, "Idempotency-Key": op}, json={"operation_id": op,
        "text": "帮我整理一份不限定星期的训练安排", "intent": "task"})
    assert response.status_code == 200
    receipt = response.json()["data"]["receipts"][0]
    assert receipt["objects"][0]["payload"]["custom_preferences"] == {"无固定日期": True}
    assert receipt["objects"][0]["source"] == "task_derived"
    assert response.json()["data"]["status"] == "completed"
    # One current plan is maintained as a business invariant.
    second = submit(client, auth, [{"action": "create", "kind": "plan", "payload": {"text": "另一份"}}])
    assert second.status_code == 409


def test_envelope_and_release_guards(client, auth):
    invalid = client.post("/api/v1/agent-actions/apply", headers=auth, json={"user_id": "other"})
    assert invalid.status_code == 422
    assert "request_id" in invalid.json() and "error" in invalid.json()
    plan = submit(client, auth, [{"action": "create", "kind": "plan",
                                 "payload": {"title": "本周安排", "nodes": [{"text": "按感觉开始"}]}}])
    assert plan.status_code == 200
    with pytest.raises(ValueError, match="Production requires"):
        Settings(environment="production", _env_file=None)


def test_return_does_not_create_messages(client, auth):
    conversation = client.post("/api/v1/conversations", headers=auth).json()["data"]["id"]
    for _ in range(3):
        assert client.get(f"/api/v1/conversations/{conversation}/messages", headers=auth).json()["data"]["items"] == []
    assert client.get("/api/v1/operations", headers=auth).json()["data"]["items"] == []


def test_export_and_delete_are_authenticated_and_isolated(client, auth, app):
    saved = submit(client, auth, [create()]).json()["data"]["objects"][0]
    other = client.post("/api/v1/auth/dev-session").json()["data"]
    other_auth = {"Authorization": "Bearer " + other["access_token"]}
    exported = client.get("/api/v1/me/export", headers=auth).json()["data"]
    assert exported["format"] == "fitmind-export-v1"
    assert exported["objects"][0]["id"] == saved["id"]
    assert client.get("/api/v1/me/export", headers=other_auth).json()["data"]["objects"] == []
    assert client.delete("/api/v1/me?confirmation=no", headers=auth).status_code == 422
    deleted = client.delete("/api/v1/me?confirmation=" + __import__("urllib.parse").parse.quote(
        "永久删除我的FitMind数据"), headers=auth)
    assert deleted.status_code == 200 and deleted.json()["data"]["deleted"] is True
    assert client.get("/api/v1/objects", headers=auth).status_code == 401
    assert client.get("/api/v1/objects", headers=other_auth).json()["data"]["items"] == []
    with app.state.sessions() as db:
        assert db.get(User, other["user_id"]) is not None
