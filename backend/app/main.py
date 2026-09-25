import hashlib
import secrets
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, text

from .agent import CompatiblePlanner, ToolGateway, run_agent
from .config import Settings
from .db import (
    AuthSession,
    Conversation,
    FitnessObject,
    ObjectRevision,
    Outbox,
    Receipt,
    Turn,
    User,
    database,
    now,
)
from .domain import DomainError, apply_changes, fingerprint, owned_object, read_context, snapshot
from .schemas import (
    ApplyRequest,
    KnowledgeCreateRequest,
    KnowledgeReviewRequest,
    KnowledgeRevisionRequest,
    MessageRequest,
)


def create_app(settings: Settings | None = None, planner=None):
    settings = settings or Settings()
    engine, sessions = database(settings.database_url)
    app = FastAPI(title="FitMind", version="0.1.0", docs_url="/docs")
    app.state.engine, app.state.sessions = engine, sessions
    app.state.planner = planner or CompatiblePlanner(settings)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def ok(request: Request, data):
        return {"data": data, "request_id": request.state.request_id}

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={
            "error": {"code": exc.code, "message": exc.message, "details": {},
                      "retryable": exc.status >= 500}, "request_id": request.state.request_id,
        })

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "error": {"code": "INVALID_INPUT", "message": "请求格式有误。", "retryable": False,
                      "details": {"fields": [list(e["loc"]) for e in exc.errors()]}},
            "request_id": request.state.request_id,
        })

    def identity(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise DomainError("UNAUTHORIZED", "请先登录。", 401)
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        with sessions() as db:
            auth = db.get(AuthSession, digest)
            if auth is None or auth.expires_at <= now():
                raise DomainError("UNAUTHORIZED", "登录已失效。", 401)
            return auth.user_id

    def check_key(operation_id, key):
        if key != str(operation_id):
            raise DomainError("IDEMPOTENCY_KEY_REQUIRED", "提交标识缺失或不一致。", 422)

    @app.get("/health")
    def health(request: Request):
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
        return ok(request, {"status": "ok", "stage": "G1", "model": settings.model_name,
                            "auth_mode": "development", "provider": settings.model_provider})

    @app.post("/api/v1/auth/dev-session")
    def dev_session(request: Request):
        if not settings.dev_login_enabled or settings.environment not in {"development", "test"}:
            raise DomainError("NOT_FOUND", "该能力未开放。", 404)
        token = secrets.token_urlsafe(40)
        with sessions.begin() as db:
            user = User()
            db.add(user)
            db.flush()
            db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               user_id=user.id, expires_at=now() + timedelta(hours=settings.session_hours)))
        return ok(request, {"access_token": token, "user_id": user.id,
                            "expires_in": settings.session_hours * 3600, "mode": "development"})

    @app.post("/api/v1/auth/wechat-login")
    def wechat_login(request: Request, code: str = Query(min_length=1, max_length=512)):
        """Exchange a wx.login code; AppSecret stays server-side and is never logged."""
        if not settings.wechat_app_secret:
            raise DomainError("AUTH_NOT_CONFIGURED", "微信登录服务尚未配置 AppSecret。", 503)
        import httpx
        try:
            response = httpx.get("https://api.weixin.qq.com/sns/jscode2session", params={
                "appid": settings.wechat_app_id, "secret": settings.wechat_app_secret,
                "js_code": code, "grant_type": "authorization_code",
            }, timeout=10)
            payload = response.json()
        except (httpx.RequestError, ValueError):
            raise DomainError("WECHAT_UNAVAILABLE", "微信登录服务暂时不可用，请重试。", 503) from None
        if not response.is_success or payload.get("errcode") or not payload.get("openid"):
            raise DomainError("WECHAT_LOGIN_FAILED", "微信登录未完成，请重试。", 401)
        # OpenID is hashed for lookup; it is never returned to the client.
        identity_key = str(uuid5(NAMESPACE_URL, settings.wechat_app_id + ":" + payload["openid"]))
        token = secrets.token_urlsafe(40)
        with sessions.begin() as db:
            user = db.scalar(select(User).where(User.id == identity_key))
            if user is None:
                user = User(id=identity_key)
                db.add(user)
                db.flush()
            db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                               expires_at=now() + timedelta(hours=settings.session_hours)))
        return ok(request, {"access_token": token, "user_id": user.id,
                            "expires_in": settings.session_hours * 3600, "mode": "wechat"})

    @app.get("/api/v1/me")
    def me(request: Request, user_id=Depends(identity)):
        with sessions() as db:
            user = db.get(User, user_id)
            return ok(request, {"id": user.id, "training_revision": user.training_revision,
                                "context_revision": user.context_revision, "mode": "development"})

    @app.get("/api/v1/me/export")
    def export_my_data(request: Request, user_id=Depends(identity)):
        """Return a machine-readable export limited strictly to the authenticated user."""
        with sessions() as db:
            objects = db.scalars(select(FitnessObject).where(
                FitnessObject.user_id == user_id).order_by(FitnessObject.created_at)).all()
            revisions = db.scalars(select(ObjectRevision).where(
                ObjectRevision.user_id == user_id,
            ).order_by(ObjectRevision.created_at)).all()
            conversations = db.scalars(select(Conversation).where(
                Conversation.user_id == user_id,
            ).order_by(Conversation.created_at)).all()
            turns = db.scalars(select(Turn).where(
                Turn.user_id == user_id,
            ).order_by(Turn.created_at)).all()
            receipts = db.scalars(select(Receipt).where(Receipt.user_id == user_id)).all()
            return ok(request, {
                "format": "fitmind-export-v1", "exported_at": now().isoformat(),
                "objects": [snapshot(row) for row in objects],
                "revisions": [{"object_id": row.object_id, "version": row.version,
                               "snapshot": row.snapshot, "evidence": row.evidence,
                               "created_at": row.created_at.isoformat()} for row in revisions],
                "conversations": [{"id": row.id, "created_at": row.created_at.isoformat()}
                                   for row in conversations],
                "messages": [row.result for row in turns],
                "operations": [row.result for row in receipts],
            })

    @app.delete("/api/v1/me")
    def delete_my_account(confirmation: str, request: Request, user_id=Depends(identity)):
        if confirmation != "永久删除我的FitMind数据":
            raise DomainError("CONFIRMATION_REQUIRED", "删除确认文本不匹配。", 422)
        with sessions.begin() as db:
            if db.get(User, user_id) is None:
                raise DomainError("NOT_FOUND", "账户不存在。", 404)
            # Remove dependencies in a single committed transaction; no user IDs
            # or other account's rows are accepted from the request.
            for model in (Turn, Receipt, ObjectRevision, AuthSession):
                db.execute(delete(model).where(model.user_id == user_id))
            db.execute(delete(Conversation).where(Conversation.user_id == user_id))
            db.execute(delete(Outbox).where(Outbox.user_id == user_id))
            db.execute(delete(FitnessObject).where(FitnessObject.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
        return ok(request, {"deleted": True})

    @app.get("/api/v1/objects")
    def objects(request: Request, limit: int = Query(default=50, ge=1, le=100),
                offset: int = Query(default=0, ge=0), user_id=Depends(identity)):
        with sessions() as db:
            return ok(request, {"items": read_context(db, user_id, limit=limit, offset=offset),
                                "offset": offset, "limit": limit})

    def require_knowledge_admin(token: str = Header(default="", alias="X-Knowledge-Admin-Token")):
        if not settings.knowledge_admin_token or not secrets.compare_digest(
                token, settings.knowledge_admin_token):
            raise DomainError("FORBIDDEN", "Knowledge administration is not available.", 403)

    @app.post("/api/v1/admin/knowledge")
    def create_knowledge(body: KnowledgeCreateRequest, request: Request,
                         _=Depends(require_knowledge_admin)):
        from .knowledge import create_document
        with sessions.begin() as db:
            doc = create_document(db, **body.model_dump())
            result = knowledge_snapshot(doc)
        return ok(request, result)

    def knowledge_snapshot(doc):
        return {"id": doc.id, "slug": doc.slug, "version": doc.version, "title": doc.title,
                "body": doc.body, "source_name": doc.source_name, "source_url": doc.source_url,
                "status": doc.status, "reviewer": doc.reviewer,
                "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
                "content_hash": doc.content_hash}

    @app.get("/api/v1/admin/knowledge")
    def list_knowledge(request: Request, status: str | None = None,
                       _=Depends(require_knowledge_admin)):
        from .db import KnowledgeDocument
        with sessions() as db:
            query = select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())
            if status:
                query = query.where(KnowledgeDocument.status == status)
            return ok(request, {"items": [knowledge_snapshot(doc) for doc in db.scalars(query.limit(200))]})

    @app.put("/api/v1/admin/knowledge/{doc_id}")
    def revise_knowledge(doc_id: UUID, body: KnowledgeRevisionRequest, request: Request,
                         _=Depends(require_knowledge_admin)):
        from .db import KnowledgeDocument
        from .knowledge import revise_document
        with sessions.begin() as db:
            doc = db.get(KnowledgeDocument, str(doc_id))
            if doc is None:
                raise DomainError("NOT_FOUND", "Knowledge document not found.", 404)
            values = body.model_dump()
            revise_document(db, doc, **values)
            result = knowledge_snapshot(doc)
        return ok(request, result)

    @app.post("/api/v1/admin/knowledge/{doc_id}/review")
    def review_knowledge(doc_id: UUID, body: KnowledgeReviewRequest, request: Request,
                         _=Depends(require_knowledge_admin)):
        from .db import KnowledgeDocument
        from .knowledge import review_document
        with sessions.begin() as db:
            doc = db.get(KnowledgeDocument, str(doc_id))
            if doc is None:
                raise DomainError("NOT_FOUND", "Knowledge document not found.", 404)
            review_document(db, doc, **body.model_dump())
            result = knowledge_snapshot(doc)
        return ok(request, result)

    @app.get("/api/v1/knowledge/search")
    def search_knowledge(request: Request, query: str = Query(min_length=2, max_length=500),
                         limit: int = Query(default=5, ge=1, le=5)):
        from .knowledge import search_published
        with sessions() as db:
            return ok(request, {"items": search_published(db, query, limit=limit)})

    @app.get("/api/v1/objects/{object_id}/revisions")
    def revisions(object_id: UUID, request: Request, user_id=Depends(identity)):
        with sessions() as db:
            owned_object(db, user_id, str(object_id))
            values = db.scalars(select(ObjectRevision).where(
                ObjectRevision.object_id == str(object_id), ObjectRevision.user_id == user_id,
            ).order_by(ObjectRevision.version.desc()).limit(100))
            return ok(request, {"items": [v.snapshot for v in values]})

    @app.post("/api/v1/agent-actions/apply")
    def apply(body: ApplyRequest, request: Request, user_id=Depends(identity),
              idempotency_key: str = Header(default="")):
        check_key(body.operation_id, idempotency_key)
        with sessions.begin() as db:
            result = apply_changes(db, user_id, body, authority="direct_user")
        return ok(request, result)

    @app.get("/api/v1/operations")
    def operations(request: Request, user_id=Depends(identity)):
        with sessions() as db:
            values = db.scalars(select(Receipt).where(Receipt.user_id == user_id).order_by(
                Receipt.created_at.desc()).limit(50))
            return ok(request, {"items": [r.result for r in values]})

    @app.post("/api/v1/conversations")
    def conversation(request: Request, user_id=Depends(identity)):
        with sessions.begin() as db:
            item = Conversation(user_id=user_id)
            db.add(item)
            db.flush()
            result = {"id": item.id}
        return ok(request, result)

    def owned_conversation(db, user_id, conversation_id):
        item = db.scalar(select(Conversation).where(
            Conversation.id == str(conversation_id), Conversation.user_id == user_id,
        ).with_for_update())
        if item is None:
            raise DomainError("NOT_FOUND", "未找到这段对话。", 404)
        return item

    @app.get("/api/v1/conversations/{conversation_id}/messages")
    def messages(conversation_id: UUID, request: Request, user_id=Depends(identity)):
        with sessions.begin() as db:
            owned_conversation(db, user_id, conversation_id)
            turns = db.scalars(select(Turn).where(Turn.conversation_id == str(conversation_id),
                                                 Turn.user_id == user_id).order_by(
                                                     Turn.created_at.desc(), Turn.id).limit(50))
            return ok(request, {"items": list(reversed([t.result for t in turns]))})

    @app.post("/api/v1/conversations/{conversation_id}/messages")
    def send(conversation_id: UUID, body: MessageRequest, request: Request,
             user_id=Depends(identity), idempotency_key: str = Header(default="")):
        check_key(body.operation_id, idempotency_key)
        # Conversation row lock serializes foreground turns. Domain tool commits use
        # independent transactions, so provider failure cannot erase a saved record.
        with sessions.begin() as db:
            owned_conversation(db, user_id, conversation_id)
            digest = fingerprint({"conversation_id": str(conversation_id),
                                  **body.model_dump(mode="json")})
            previous = db.scalar(select(Turn).where(Turn.user_id == user_id,
                                                    Turn.operation_id == str(body.operation_id)))
            if previous:
                if previous.fingerprint != digest:
                    raise DomainError("IDEMPOTENCY_CONFLICT", "这次重试与原消息不同。")
                return ok(request, previous.result)
            recent = list(db.scalars(select(Turn).where(
                Turn.conversation_id == str(conversation_id), Turn.user_id == user_id,
            ).order_by(Turn.created_at.desc(), Turn.id).limit(12)))
            history = []
            for turn in reversed(recent):
                history.extend([{"role": "user", "content": turn.result["text"]},
                                {"role": "assistant", "content": turn.result["reply"]}])
            history.append({"role": "user", "content": body.text})
            gateway = ToolGateway(sessions, user_id, str(body.operation_id), body.text, body.intent)
            result = run_agent(app.state.planner, gateway, history)
            result.update({"operation_id": str(body.operation_id), "text": body.text,
                           "intent": body.intent, "model": settings.model_name})
            db.add(Turn(conversation_id=str(conversation_id), user_id=user_id,
                        operation_id=str(body.operation_id), fingerprint=digest, result=result))
        return ok(request, result)

    return app


app = create_app()
