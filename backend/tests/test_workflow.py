from app.workflow import classify, cosine, normalize


def test_intents_and_normalization():
    assert normalize("  Why   did OUR bill increase? ") == "why did our bill increase?"
    assert classify("Why did our bill increase?") == "invoice"
    assert classify("What is our P1 SLA?") == "sla"
    assert classify("Is SSO included?") == "security"


def test_cosine_rejects_incompatible_vectors():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    assert cosine([1], [1, 0]) == 0

