import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import Settings
from app.db import Base
from app.main import create_app


class FakePlanner:
    def complete(self, messages, tools):
        return {"role": "assistant", "content": "已了解。今天训练后的感受如何？"}


@pytest.fixture
def app():
    url = os.getenv("FITMIND_TEST_DATABASE_URL", "postgresql+psycopg://postgres@127.0.0.1:55432/fitmind")
    engine = create_engine(url)
    schema = "test_" + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    # Isolated schema per test; never truncate the developer's database.
    scoped_url = url + ("&" if "?" in url else "?") + f"options=-csearch_path%3D{schema}"
    application = create_app(Settings(database_url=scoped_url, environment="test", dev_login_enabled=True,
                                      knowledge_admin_token="test-secret"),
                             planner=FakePlanner())
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as value:
        yield value


@pytest.fixture
def auth(client):
    data = client.post("/api/v1/auth/dev-session").json()["data"]
    return {"Authorization": "Bearer " + data["access_token"]}
