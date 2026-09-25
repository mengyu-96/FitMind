def test_knowledge_requires_admin_and_only_published_searches(client, app):
    from app.config import Settings
    app.state  # fixture-created app settings are intentionally immutable
    # A separate app configured with an admin token shares the isolated test schema.
    from app.main import create_app
    admin_app = create_app(Settings(database_url=str(app.state.engine.url), environment="test",
                                    dev_login_enabled=True, knowledge_admin_token="test-secret"))
    from fastapi.testclient import TestClient
    with TestClient(admin_app) as admin:
        doc = {"slug": "strength-basics", "title": "Strength basics",
               "body": "Progress gradually and allow recovery between demanding sessions.",
               "source_name": "Reviewed guide", "source_url": "https://example.org/guide"}
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
