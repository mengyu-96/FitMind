import hashlib
import json
from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import FitnessObject, ObjectRevision, Outbox, Receipt, User, now, uid
from .schemas import ApplyRequest


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def lock_user(db: Session, user_id: str) -> User:
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise DomainError("UNAUTHORIZED", "登录已失效。", 401)
    return user


def owned_object(db: Session, user_id: str, object_id: str) -> FitnessObject:
    obj = db.scalar(select(FitnessObject).where(
        FitnessObject.id == object_id, FitnessObject.user_id == user_id,
    ))
    if obj is None:
        raise DomainError("NOT_FOUND", "未找到这条内容。", 404)
    return obj


def snapshot(obj: FitnessObject) -> dict:
    return {
        "id": obj.id, "kind": obj.kind, "payload": deepcopy(obj.payload),
        "version": obj.version, "lifecycle": obj.lifecycle,
        "source": obj.source, "purpose": obj.purpose,
    }


def read_context(db: Session, user_id: str, *, limit: int = 50, offset: int = 0,
                 kind: str | None = None) -> list[dict]:
    query = select(FitnessObject).where(
        FitnessObject.user_id == user_id, FitnessObject.lifecycle == "active",
    )
    if kind:
        query = query.where(FitnessObject.kind == kind)
    objects = db.scalars(query.order_by(FitnessObject.updated_at.desc(), FitnessObject.id)
                          .offset(offset).limit(limit))
    return [snapshot(obj) for obj in objects]


def apply_changes(db: Session, user_id: str, body: ApplyRequest, *, authority: str) -> dict:
    """Caller owns the transaction; one lock serializes this user's mutations.

    Authority is injected by the trusted route/tool gateway, never a model argument.
    G1 only enables explicit user editing and the explicit save-record task.
    """
    if authority not in {"direct_user", "record_task", "current_task"}:
        raise DomainError("AUTHORITY_REQUIRED", "当前任务尚未授权这项修改。", 403)
    if authority == "record_task" and any(op.action != "create" or op.kind != "activity"
                                          for op in body.operations):
        raise DomainError("OUTSIDE_TASK", "本轮仅授权保存记录。", 403)
    if authority == "current_task" and any(op.kind == "mandate" for op in body.operations):
        raise DomainError("OUTSIDE_TASK", "持续自主委托尚未开放。", 403)
    user = lock_user(db, user_id)
    operation_id = str(body.operation_id)
    digest = fingerprint({"body": body.model_dump(mode="json"), "authority": authority})
    previous = db.get(Receipt, (user_id, operation_id))
    if previous:
        if previous.fingerprint != digest:
            raise DomainError("IDEMPOTENCY_CONFLICT", "重试标识已用于另一项修改。")
        return previous.result

    changed, activity_changed, context_changed = [], False, False
    seen = set()
    for change in body.operations:
        if change.action == "create":
            if authority == "current_task" and change.kind not in {"plan", "profile", "activity"}:
                raise DomainError("OUTSIDE_TASK", "当前任务不能创建这类对象。", 403)
            if change.kind == "plan" and db.scalar(select(FitnessObject.id).where(
                FitnessObject.user_id == user_id, FitnessObject.kind == "plan",
                FitnessObject.lifecycle == "active",
            ).limit(1)):
                raise DomainError("ACTIVE_PLAN_EXISTS", "已有当前主计划，请在原计划上调整。")
            obj = FitnessObject(
                id=uid(), user_id=user_id, kind=change.kind, payload=deepcopy(change.payload),
                version=1, lifecycle="active",
                source="task_derived" if authority == "current_task" else "user_report",
                purpose="personal_coaching",
            )
            db.add(obj)
        else:
            obj = owned_object(db, user_id, str(change.object_id))
            if authority == "current_task" and obj.kind not in {"plan", "profile", "activity"}:
                raise DomainError("OUTSIDE_TASK", "当前任务不能修改这类对象。", 403)
            if obj.id in seen:
                raise DomainError("DUPLICATE_TARGET", "一次原子修改不能重复指定同一对象。", 422)
            if obj.version != change.expected_version:
                raise DomainError("VERSION_CONFLICT", "内容已更新，请查看最新版本后重试。")
            if change.action == "replace":
                obj.payload = deepcopy(change.payload)
            else:
                old = db.scalar(select(ObjectRevision).where(
                    ObjectRevision.user_id == user_id, ObjectRevision.object_id == obj.id,
                    ObjectRevision.version == change.restore_version,
                ))
                if old is None or change.restore_version >= obj.version:
                    raise DomainError("INVALID_RESTORE", "只能恢复到这条内容已有的更早版本。")
                obj.payload = deepcopy(old.snapshot["payload"])
            obj.version += 1
        seen.add(obj.id)
        obj.updated_at = now()
        value = snapshot(obj)
        db.flush()
        db.add(ObjectRevision(
            object_id=obj.id, user_id=user_id, version=obj.version,
            snapshot=value, operation_id=operation_id,
            evidence={"type": "explicit_task_instruction" if authority == "current_task"
                      else "explicit_user_input", "authority": authority},
        ))
        changed.append(value)
        activity_changed |= obj.kind == "activity"
        context_changed |= obj.kind != "activity"
    user.training_revision += int(activity_changed)
    user.context_revision += int(context_changed)
    result = {
        "operation_id": operation_id, "objects": changed,
        "training_revision": user.training_revision, "context_revision": user.context_revision,
        "undoable": all(obj["version"] > 1 for obj in changed),
    }
    db.add(Receipt(user_id=user_id, operation_id=operation_id, fingerprint=digest, result=result))
    db.add(Outbox(user_id=user_id, event_type="objects.changed", payload=result))
    db.flush()
    return result
