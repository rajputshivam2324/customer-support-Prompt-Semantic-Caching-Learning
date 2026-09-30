import json
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.models import Base, Invoice, KnowledgeDoc, RequestTrace
from app.seed import seed
from app.workflow import SupportWorkflow


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, seconds, value):
        self.values[key] = value


class FakeEmbeddings:
    def embed_query(self, text):
        return [1.0, 0.0] if "sla" in text.lower() or "p1" in text.lower() else [0.0, 1.0]

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        return SimpleNamespace(content="The answer is grounded in the supplied records.", usage_metadata={"input_tokens": 100, "output_tokens": 12})


def test_cache_paths_and_tenant_scopes():
    engine = create_engine("sqlite://")
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed(db)
        settings = SimpleNamespace(gemini_model="gemini-2.5-flash", google_api_key="unused", embedding_model="unused", semantic_threshold=0.96, cache_ttl_seconds=3600)
        cache, llm = FakeRedis(), FakeLLM()
        flow = SupportWorkflow(settings, db, cache, llm=llm, embeddings=FakeEmbeddings())

        first = flow.run("acme", "acme-customer", "What is our P1 SLA?")
        exact = flow.run("acme", "acme-customer", "What is our P1 SLA?")
        semantic = flow.run("acme", "acme-customer", "Could you explain our P1 SLA?")
        other_tenant = flow.run("globex", "globex-customer", "What is our P1 SLA?")
        invoice = flow.run("acme", "acme-customer", "Why did our bill increase in April?")
        invoice_again = flow.run("acme", "acme-customer", "Why did our bill increase in April?")

        assert [x["source"] for x in (first, exact, semantic, other_tenant, invoice, invoice_again)] == ["rag_llm", "exact_cache", "semantic_cache", "rag_llm", "tool_llm", "exact_cache"]
        assert llm.calls == 3
        assert first["citations"] == semantic["citations"]
        assert exact["tokens_saved"] == 112
        assert semantic["similarity"] == 1.0
        assert db.query(RequestTrace).count() == 6
        assert any(e["step"] == "invoice_tool" for e in invoice["events"])
        assert any(e["step"] == "invoice_snapshot" for e in invoice_again["events"])

        policy = db.get(KnowledgeDoc, "sla")
        old_fingerprint = policy.embedding_fingerprint
        policy.content += " Updated demo response window."
        db.commit()
        refreshed = flow.run("acme", "acme-customer", "What is our P1 SLA?")
        assert refreshed["source"] == "rag_llm"
        assert policy.embedding_fingerprint != old_fingerprint
        assert llm.calls == 4

        april = db.get(Invoice, "inv-acme-apr")
        april.amount = 700
        db.commit()
        changed = flow.run("acme", "acme-customer", "Why did our bill increase in April?")
        assert changed["source"] == "tool_llm"
        assert llm.calls == 5

        follow_up = flow.run("acme", "acme-customer", "Can you tell me more about April usage?", history=[{"role": "user", "content": "Why did our bill increase in April?"}, {"role": "assistant", "content": "It was metered usage."}])
        assert follow_up["source"] == "tool_llm"
        assert any("follow-up" in e["detail"] for e in follow_up["events"])
