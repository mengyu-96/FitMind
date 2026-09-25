from uuid import uuid4


def test_knowledge_requires_admin_and_only_published_searches(client, app):
    doc = {"slug": "strength-basics", "title": "Strength basics",
           "body": "Progress gradually and allow recovery between demanding sessions.",
           "source_name": "Reviewed guide", "source_url": "https://example.org/guide"}
    admin = client
    assert admin.post("/api/v1/admin/knowledge", json=doc).status_code == 403
    headers = {"X-Knowledge-Admin-Token": "test-secret"}
    created = admin.post("/api/v1/admin/knowledge", json=doc, headers=headers)
    assert created.status_code == 200
    item = created.json()["data"]
    assert item["status"] == "draft"
    assert admin.get("/api/v1/knowledge/search", params={"query": "strength recovery"}).json()["data"]["items"] == []
    review = admin.post(f"/api/v1/admin/knowledge/{item['id']}/review", headers=headers,
                            json={"decision": "approve", "reviewer": "editor"})
    assert review.json()["data"]["status"] == "published"
    found = admin.get("/api/v1/knowledge/search", params={"query": "strength recovery"}).json()["data"]["items"]
    assert found and found[0]["source_name"] == "Reviewed guide"
    revised = admin.put(f"/api/v1/admin/knowledge/{item['id']}", headers=headers, json={
            "expected_version": 1, "title": "Strength basics revised",
            "body": "Progress gradually and keep recovery time.",
            "source_name": "Reviewed guide", "source_url": "https://example.org/guide"})
    assert revised.status_code == 409
    withdrawn = admin.post(f"/api/v1/admin/knowledge/{item['id']}/review", headers=headers,
                               json={"decision": "withdraw", "reviewer": "editor"})
    assert withdrawn.json()["data"]["status"] == "withdrawn"
    assert admin.get("/api/v1/knowledge/search", params={"query": "strength recovery"}).json()["data"]["items"] == []


def test_knowledge_rejects_malformed_admin_payload_without_write(client, app):
    admin = client
    headers = {"X-Knowledge-Admin-Token": "test-secret"}
    response = admin.post("/api/v1/admin/knowledge", headers=headers,
                              json={"slug": "bad", "title": 12, "body": "x", "source_name": "source"})
    assert response.status_code == 422
    assert admin.get("/api/v1/admin/knowledge", headers=headers).json()["data"]["items"] == []


def test_agent_can_retrieve_only_reviewed_knowledge(client, app, auth):
    admin = client
    headers = {"X-Knowledge-Admin-Token": "test-secret"}
    created = admin.post("/api/v1/admin/knowledge", headers=headers, json={
            "slug": "agent-recovery", "title": "Recovery", "body": "Recovery needs rest.",
            "source_name": "Editorial review", "source_url": "https://example.org/recovery"})
    doc_id = created.json()["data"]["id"]
    admin.post(f"/api/v1/admin/knowledge/{doc_id}/review", headers=headers,
                   json={"decision": "approve", "reviewer": "editor"})

    conversation = client.post("/api/v1/conversations", headers=auth).json()["data"]["id"]
    class KnowledgePlanner:
        def complete(self, messages, tools):
            if any(message["role"] == "tool" for message in messages):
                return {"role": "assistant", "content": "已找到经审核来源。"}
            assert any(item["function"]["name"] == "search_knowledge" for item in tools)
            return {"role": "assistant", "tool_calls": [{"id": str(uuid4()), "type": "function",
                "function": {"name": "search_knowledge", "arguments":
                              '{"query":"recovery rest","limit":3}'}}]}
    app.state.planner = KnowledgePlanner()
    operation_id = str(uuid4())
    response = client.post(f"/api/v1/conversations/{conversation}/messages",
                           headers={**auth, "Idempotency-Key": operation_id},
                           json={"operation_id": operation_id, "text": "如何恢复？", "intent": "chat"})
    assert response.status_code == 200
    assert response.json()["data"]["reply"] == "已找到经审核来源。"
