from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import VECTOR


VECTOR_768 = JSON().with_variant(VECTOR(768), "postgresql")


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(50))
    region: Mapped[str] = mapped_column(String(50))


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30))
    billing_period: Mapped[str] = mapped_column(String(20))
    line_items: Mapped[list] = mapped_column(JSON)


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_vector: Mapped[list | None] = mapped_column(VECTOR_768, nullable=True)
    embedding_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SemanticEntry(Base):
    __tablename__ = "semantic_entries"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    customer_scope: Mapped[str] = mapped_column(String(160), index=True)
    intent: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[list] = mapped_column(JSON)
    embedding_vector: Mapped[list | None] = mapped_column(VECTOR_768, nullable=True)
    original_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RequestTrace(Base):
    __tablename__ = "request_traces"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    operator_id: Mapped[str | None] = mapped_column(ForeignKey("operators.id"), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), index=True)
    events: Mapped[list] = mapped_column(JSON)
    citations: Mapped[list] = mapped_column(JSON)
    latency_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    tokens_saved: Mapped[int] = mapped_column(Integer, default=0)
    similarity: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Operator(Base):
    __tablename__ = "operators"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: str(uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(ForeignKey("request_traces.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
