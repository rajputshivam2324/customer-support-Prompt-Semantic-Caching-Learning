from contextlib import asynccontextmanager
from typing import Annotated

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import issue_session, operator_for_token, revoke_session, verify_password
from .config import Settings
from .db import make_session_factory
from .models import ChatMessage, Conversation, Customer, Operator, RequestTrace, Tenant, now
from .seed import seed
from .workflow import SupportWorkflow


settings = Settings()
SessionLocal = make_session_factory(settings)
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        seed(db, settings)
    yield


app = FastAPI(title="AI Support Gateway", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


def session():
    with SessionLocal() as db:
        yield db


DB = Annotated[Session, Depends(session)]


def current_operator(db: DB, authorization: Annotated[str | None, Header()] = None) -> Operator:
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else ""
    operator = operator_for_token(db, token) if token else None
    if not operator:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    if operator.role not in ("admin", "agent"):
        raise HTTPException(status_code=403, detail="Operator access required")
    return operator


User = Annotated[Operator, Depends(current_operator)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class CreateConversationRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=40)


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=40)
    question: str = Field(min_length=2, max_length=2000)


def user_data(user: Operator, db: Session):
    tenant = db.get(Tenant, user.tenant_id)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "tenant_id": user.tenant_id, "tenant_name": tenant.name}


def conversation_data(row: Conversation):
    return {"id": row.id, "customer_id": row.customer_id, "title": row.title, "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}


def owned_conversation(db: Session, conversation_id: str, user: Operator) -> Conversation:
    row = db.get(Conversation, conversation_id)
    if not row or row.tenant_id != user.tenant_id or row.operator_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return row


def trace_data(t: RequestTrace):
    return {"id": t.id, "tenant_id": t.tenant_id, "operator_id": t.operator_id, "conversation_id": t.conversation_id, "customer_id": t.customer_id, "question": t.question, "answer": t.answer, "source": t.source, "events": t.events, "citations": t.citations, "latency_ms": t.latency_ms, "input_tokens": t.input_tokens, "output_tokens": t.output_tokens, "tokens_saved": t.tokens_saved, "similarity": float(t.similarity) if t.similarity is not None else None, "model": t.model, "created_at": t.created_at.isoformat()}


def trace_filter(user: Operator):
    return RequestTrace.tenant_id == user.tenant_id if user.role == "admin" else RequestTrace.operator_id == user.id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/auth/login")
def login(body: LoginRequest, db: DB):
    operator = db.scalar(select(Operator).where(Operator.email == body.email.strip().lower()))
    if not operator or not verify_password(body.password, operator.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = issue_session(db, operator)
    return {"token": token, "expires_in": 28800, "user": user_data(operator, db)}


@app.post("/v1/auth/logout")
def logout(user: User, db: DB, authorization: Annotated[str | None, Header()] = None):
    if authorization:
        revoke_session(db, authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@app.get("/v1/auth/me")
def me(user: User, db: DB):
    return user_data(user, db)


@app.get("/v1/customers")
def customers(user: User, db: DB):
    rows = db.scalars(select(Customer).where(Customer.tenant_id == user.tenant_id).order_by(Customer.name)).all()
    return [{"id": c.id, "name": c.name, "email": c.email, "plan": c.plan, "region": c.region} for c in rows]


@app.get("/v1/conversations")
def conversations(user: User, db: DB):
    rows = db.scalars(select(Conversation).where(Conversation.tenant_id == user.tenant_id, Conversation.operator_id == user.id).order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [conversation_data(row) for row in rows]


@app.post("/v1/conversations", status_code=201)
def create_conversation(body: CreateConversationRequest, user: User, db: DB):
    customer = db.get(Customer, body.customer_id)
    if not customer or customer.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    row = Conversation(tenant_id=user.tenant_id, operator_id=user.id, customer_id=customer.id)
    db.add(row)
    db.commit()
    return conversation_data(row)


@app.get("/v1/conversations/{conversation_id}")
def conversation(conversation_id: str, user: User, db: DB):
    row = owned_conversation(db, conversation_id, user)
    traces = db.scalars(select(RequestTrace).where(RequestTrace.conversation_id == row.id, RequestTrace.operator_id == user.id).order_by(RequestTrace.created_at)).all()
    return {**conversation_data(row), "traces": [trace_data(item) for item in traces]}


@app.post("/v1/chat")
def chat(body: ChatRequest, user: User, db: DB):
    conversation = owned_conversation(db, body.conversation_id, user)
    messages = db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation.id).order_by(ChatMessage.created_at.desc()).limit(6)).all()
    history = [{"role": item.role, "content": item.content} for item in reversed(messages)]
    state = SupportWorkflow(settings, db, redis_client).run(user.tenant_id, conversation.customer_id, body.question, operator_id=user.id, conversation_id=conversation.id, history=history)
    db.add(ChatMessage(conversation_id=conversation.id, role="user", content=body.question))
    db.add(ChatMessage(conversation_id=conversation.id, role="assistant", content=state["answer"], trace_id=state["trace_id"]))
    if conversation.title == "New conversation":
        conversation.title = body.question.strip()[:100]
    conversation.updated_at = now()
    db.commit()
    return {"answer": state["answer"], "source": state["source"], "trace_id": state["trace_id"], "conversation_id": conversation.id, "latency_ms": state["latency_ms"], "similarity": state.get("similarity"), "citations": state.get("citations", []), "usage": {"input_tokens": state.get("input_tokens", 0), "output_tokens": state.get("output_tokens", 0), "tokens_saved": state.get("tokens_saved", 0)}}


@app.get("/v1/traces")
def traces(user: User, db: DB, limit: int = 25):
    limit = max(1, min(limit, 100))
    rows = db.scalars(select(RequestTrace).where(trace_filter(user)).order_by(RequestTrace.created_at.desc()).limit(limit)).all()
    return [trace_data(row) for row in rows]


@app.get("/v1/traces/{trace_id}")
def trace(trace_id: str, user: User, db: DB):
    row = db.get(RequestTrace, trace_id)
    if not row or row.tenant_id != user.tenant_id or (user.role != "admin" and row.operator_id != user.id):
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace_data(row)


@app.get("/v1/metrics")
def metrics(user: User, db: DB):
    rows = db.execute(select(RequestTrace.source, func.count(), func.sum(RequestTrace.tokens_saved)).where(trace_filter(user)).group_by(RequestTrace.source)).all()
    counts = {source: count for source, count, _ in rows}
    total = sum(counts.values())
    saved = sum(tokens or 0 for _, _, tokens in rows)
    latencies = sorted(db.scalars(select(RequestTrace.latency_ms).where(trace_filter(user))).all())
    p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))] if latencies else 0
    return {"requests": total, "sources": counts, "cache_hit_rate": round((counts.get("exact_cache", 0) + counts.get("semantic_cache", 0)) / total, 3) if total else 0, "tokens_saved_estimate": saved, "avg_latency_ms": round(sum(latencies) / total) if total else 0, "p95_latency_ms": p95}
