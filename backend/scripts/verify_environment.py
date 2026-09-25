"""Local dependency smoke checks; no external model or database requests."""

import json
import os
import sys
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field


class ConfirmationState(TypedDict, total=False):
    proposal: str
    approved: bool


class TrainingInput(BaseModel):
    reps: int = Field(ge=1, le=100)


def verify() -> dict:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    expected_prefix = Path(__file__).resolve().parents[2] / ".conda" / "fitmind-backend"
    assert Path(sys.prefix).resolve() == expected_prefix.resolve(), (
        "Use the project Conda interpreter, not the base environment."
    )
    assert sys.version_info[:2] == (3, 12), "Python 3.12 is required."

    packages = (
        "fastapi",
        "uvicorn",
        "pydantic",
        "pydantic-settings",
        "sqlalchemy",
        "alembic",
        "psycopg",
        "pgvector",
        "redis",
        "httpx",
        "langgraph",
        "langgraph-checkpoint-postgres",
        "pytest",
        "pytest-asyncio",
        "ruff",
    )
    for module in (
        "sqlalchemy",
        "alembic",
        "psycopg",
        "psycopg_pool",
        "pgvector.sqlalchemy",
        "redis.asyncio",
        "langgraph.checkpoint.postgres.aio",
        "pydantic_settings",
    ):
        import_module(module)

    app = FastAPI()

    @app.post("/smoke/training")
    def validate_training(body: TrainingInput):
        return {"reps": body.reps}

    with TestClient(app) as client:
        response = client.post("/smoke/training", json={"reps": 10})
        assert response.status_code == 200 and response.json() == {"reps": 10}
        assert client.post("/smoke/training", json={"reps": 0}).status_code == 422

    def request_confirmation(state: ConfirmationState):
        # Nothing with side effects belongs before interrupt: this node restarts.
        approved = interrupt({"proposal": state["proposal"]})
        if type(approved) is not bool:
            raise ValueError("Confirmation must be boolean.")
        return {"approved": approved}

    builder = StateGraph(ConfirmationState)
    builder.add_node("confirm", request_confirmation)
    builder.add_edge(START, "confirm")
    builder.add_edge("confirm", END)
    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    first = {"configurable": {"thread_id": "smoke-a"}}
    second = {"configurable": {"thread_id": "smoke-b"}}

    pending_a = graph.invoke({"proposal": "plan-a"}, config=first)
    pending_b = graph.invoke({"proposal": "plan-b"}, config=second)
    assert pending_a["__interrupt__"] and pending_b["__interrupt__"]
    assert "approved" not in graph.get_state(first).values

    # Recompile using the same in-memory saver: verifies graph API resumption,
    # not process restart persistence (which requires PostgreSQL integration).
    resumed_graph = builder.compile(checkpointer=checkpointer)
    accepted = resumed_graph.invoke(Command(resume=True), config=first)
    assert accepted["proposal"] == "plan-a" and accepted["approved"] is True
    assert graph.get_state(second).values["proposal"] == "plan-b"
    assert "approved" not in graph.get_state(second).values
    rejected = resumed_graph.invoke(Command(resume=False), config=second)
    assert rejected["proposal"] == "plan-b" and rejected["approved"] is False

    return {
        "status": "passed",
        "python": sys.version.split()[0],
        "prefix": sys.prefix,
        "versions": {package: version(package) for package in packages},
        "checks": [
            "project_interpreter",
            "dependency_imports",
            "fastapi_local_request",
            "pydantic_rejection",
            "graph_interrupt",
            "graph_resume_accept",
            "graph_resume_reject",
            "graph_thread_state_separation",
        ],
        "not_verified": [
            "postgresql_or_redis_connectivity",
            "durable_restart",
            "business_idempotency",
            "authentication",
            "real_model_calls",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
