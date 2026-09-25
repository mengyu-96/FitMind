import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Change(StrictModel):
    action: Literal["create", "replace", "undo"]
    object_id: UUID | None = None
    kind: str | None = Field(default=None, min_length=1, max_length=100)
    payload: dict[str, Any] | None = None
    expected_version: int | None = Field(default=None, ge=1)
    restore_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def valid_change(self):
        if self.action == "create":
            if self.object_id or self.expected_version or self.restore_version:
                raise ValueError("Create cannot target an existing version.")
            if self.kind is None or self.payload is None:
                raise ValueError("Create requires kind and payload.")
        else:
            if not self.object_id or not self.expected_version or self.kind is not None:
                raise ValueError("Existing objects require object_id/expected_version, not kind.")
            if self.action == "replace" and (self.payload is None or self.restore_version):
                raise ValueError("Replace requires payload only.")
            if self.action == "undo" and (not self.restore_version or self.payload is not None):
                raise ValueError("Undo requires restore_version only.")
        if self.payload is not None:
            encoded = json.dumps(self.payload, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode()) > 32768:
                raise ValueError("Payload exceeds 32 KiB.")
        return self


class ApplyRequest(StrictModel):
    operation_id: UUID
    operations: list[Change] = Field(min_length=1, max_length=20)


class MessageRequest(StrictModel):
    operation_id: UUID
    text: str = Field(min_length=1, max_length=8000)
    intent: Literal["chat", "record", "task"] = "chat"

    @model_validator(mode="after")
    def nonempty(self):
        if not self.text.strip():
            raise ValueError("Text cannot be blank.")
        return self


class KnowledgeCreateRequest(StrictModel):
    slug: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=12000)
    source_name: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)


class KnowledgeRevisionRequest(StrictModel):
    expected_version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=12000)
    source_name: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)


class KnowledgeReviewRequest(StrictModel):
    decision: Literal["approve", "reject", "withdraw"]
    reviewer: str = Field(min_length=1, max_length=200)
