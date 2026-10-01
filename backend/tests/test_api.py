import importlib

import pytest
from fastapi import HTTPException

from app.auth import hash_password, operator_for_token
from app.models import Operator, RequestTrace
from app.seed import seed


def test_operator_auth_and_conversation_ownership(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only-key")
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_OPERATOR_PASSWORD", "test-password")
    main = importlib.import_module("app.main")

    with main.SessionLocal() as db:
        seed(db, main.settings)
        with pytest.raises(HTTPException) as denied:
            main.current_operator(db, None)
        assert denied.value.status_code == 401

        response = main.login(main.LoginRequest(email="demo@relay.example", password="test-password"), db)
        token = response["token"]
        user = main.current_operator(db, f"Bearer {token}")
        assert user.email == "demo@relay.example"
        assert [row["id"] for row in main.customers(user, db)] == ["demo-customer"]

        conversation = main.create_conversation(main.CreateConversationRequest(customer_id="demo-customer"), user, db)
        assert main.conversation(conversation["id"], user, db)["traces"] == []
        other = Operator(tenant_id="demo", email="other@relay.example", name="Other", role="agent", password_hash=hash_password("other-password"))
        db.add(other)
        db.commit()
        with pytest.raises(HTTPException) as hidden:
            main.conversation(conversation["id"], other, db)
        assert hidden.value.status_code == 404

        trace = RequestTrace(tenant_id="demo", operator_id=user.id, conversation_id=conversation["id"], customer_id="demo-customer", question="Test?", answer="Test.", source="llm", events=[], citations=[], latency_ms=1)
        db.add(trace)
        db.commit()
        assert main.trace(trace.id, user, db)["operator_id"] == user.id
        with pytest.raises(HTTPException) as hidden_trace:
            main.trace(trace.id, other, db)
        assert hidden_trace.value.status_code == 404

        main.logout(user, db, f"Bearer {token}")
        assert operator_for_token(db, token) is None
        rotated_token = main.login(main.LoginRequest(email="demo@relay.example", password="test-password"), db)["token"]
        seed(db, main.settings.model_copy(update={"demo_operator_password": "rotated-password"}))
        assert operator_for_token(db, rotated_token) is None
        assert main.login(main.LoginRequest(email="demo@relay.example", password="rotated-password"), db)["user"]["id"] == user.id
