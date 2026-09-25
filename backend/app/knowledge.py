import hashlib
import re
from datetime import timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import KnowledgeDocument, now, uid
from .domain import DomainError


def clean_text(value: str, limit: int) -> str:
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value or len(value) > limit:
        raise DomainError("INVALID_CONTENT", "内容为空或超出允许长度。", 422)
    return value


def create_document(db: Session, *, slug: str, title: str, body: str,
                    source_name: str, source_url: str | None = None) -> KnowledgeDocument:
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,199}", slug):
        raise DomainError("INVALID_SLUG", "文档编号格式不正确。", 422)
    if db.scalar(select(KnowledgeDocument.id).where(KnowledgeDocument.slug == slug)):
        raise DomainError("SLUG_EXISTS", "该文档编号已存在。", 409)
    title, body, source_name = (clean_text(title, 240), clean_text(body, 12000),
                                clean_text(source_name, 300))
    if source_url and (not source_url.startswith("https://") or len(source_url) > 2000):
        raise DomainError("INVALID_SOURCE", "来源地址格式不正确。", 422)
    doc = KnowledgeDocument(id=uid(), slug=slug, version=1, title=title, body=body,
                             source_name=source_name, source_url=source_url,
                             content_hash=hashlib.sha256(body.encode()).hexdigest(),
                             status="draft")
    db.add(doc)
    db.flush()
    return doc


def revise_document(db: Session, doc: KnowledgeDocument, *, expected_version: int,
                    title: str, body: str, source_name: str, source_url: str | None):
    if doc.status not in {"draft", "rejected"}:
        raise DomainError("INVALID_TRANSITION", "Only unpublished documents can be edited.", 409)
    if doc.version != expected_version:
        raise DomainError("VERSION_CONFLICT", "文档已更新，请重新载入。", 409)
    doc.version += 1
    doc.title = clean_text(title, 240)
    doc.body = clean_text(body, 12000)
    doc.source_name = clean_text(source_name, 300)
    doc.source_url = source_url
    if source_url and (not source_url.startswith("https://") or len(source_url) > 2000):
        raise DomainError("INVALID_SOURCE", "Source URL must use HTTPS.", 422)
    doc.content_hash = hashlib.sha256(doc.body.encode()).hexdigest()
    doc.status = "draft"
    doc.reviewer = None
    doc.reviewed_at = None
    doc.updated_at = now()
    return doc


def review_document(db: Session, doc: KnowledgeDocument, *, decision: str, reviewer: str):
    if decision not in {"approve", "reject", "withdraw"}:
        raise DomainError("INVALID_REVIEW", "审核动作无效。", 422)
    if not reviewer.strip() or len(reviewer) > 200:
        raise DomainError("INVALID_REVIEWER", "审核人不能为空。", 422)
    if decision == "approve":
        if doc.status not in {"draft", "rejected"}:
            raise DomainError("INVALID_TRANSITION", "当前文档状态不能直接发布。", 409)
        doc.status = "published"
    elif decision == "reject":
        if doc.status != "draft":
            raise DomainError("INVALID_TRANSITION", "只能驳回待审版本。", 409)
        doc.status = "rejected"
    else:
        if doc.status != "published":
            raise DomainError("INVALID_TRANSITION", "只有已发布版本可以撤回。", 409)
        doc.status = "withdrawn"
    doc.reviewer = reviewer.strip()
    doc.reviewed_at = now()
    doc.updated_at = now()
    return doc


def search_published(db: Session, query: str, *, limit: int = 5):
    terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]{2,}", query.lower()) if term]
    if not terms:
        return []
    docs = list(db.scalars(select(KnowledgeDocument).where(
        KnowledgeDocument.status == "published",
    ).order_by(KnowledgeDocument.updated_at.desc()).limit(300)))
    scored = []
    for doc in docs:
        haystack = (doc.title + " " + doc.body).lower()
        overlap = sum(1 for term in set(terms) if term in haystack)
        if overlap:
            score = overlap / len(set(terms))
            scored.append((score, doc))
        else:
            similarity = SequenceMatcher(None, " ".join(terms), haystack[:1200]).ratio()
            if similarity >= 0.08:
                scored.append((similarity, doc))
    scored.sort(key=lambda item: (-item[0], item[1].slug))
    return [{"id": doc.id, "slug": doc.slug, "version": doc.version, "title": doc.title,
             "excerpt": doc.body[:1200], "source_name": doc.source_name,
             "source_url": doc.source_url, "reviewer": doc.reviewer,
             "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
             "score": round(score, 4)} for score, doc in scored[:limit]]


def stale_reviewed_doc(doc: KnowledgeDocument) -> bool:
    return doc.reviewed_at is None or doc.reviewed_at < now() - timedelta(days=3650)
