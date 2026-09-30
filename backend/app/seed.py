from sqlalchemy.orm import Session

from .auth import hash_password, verify_password
from .config import Settings
from .models import Customer, Invoice, KnowledgeDoc, Operator, Tenant
from sqlalchemy import select


TENANTS = [
    ("demo", "Demo Workspace", "Enterprise", "us-east"),
    ("acme", "Acme Corp", "Enterprise", "us-east"),
    ("globex", "Globex", "Business", "eu-west"),
    ("wayne", "Wayne Industries", "Enterprise", "us-east"),
    ("stark", "Stark Systems", "Enterprise", "us-west"),
    ("umbrella", "Umbrella Labs", "Business", "eu-west"),
]

DOCS = [
    ("billing-policy", "Billing policy", "Invoices are issued on the first day of each month. Subscription seats are charged in advance. Usage above the included allowance appears as a separate metered usage line item. Seat changes during a period are prorated. Account admins can download invoices in the billing portal."),
    ("refund-policy", "Refund policy", "Annual subscriptions may be refunded within 14 days of the initial purchase. Renewals and metered usage are not refundable. A billing admin can request a review through support within 30 days of an invoice."),
    ("subscription-policy", "Subscription policy", "Admins may add seats at any time; added seats are prorated for the remaining billing period. Seat reductions take effect at the next renewal. Cancellation must be submitted by an account admin before renewal and access continues through the paid period."),
    ("sla", "Service level agreement", "Enterprise plans include 99.9% monthly uptime and a one-hour initial response target for P1 incidents. Business plans include 99.5% monthly uptime and a four-hour initial response target for P1 incidents. Service credits are reviewed after an eligible outage."),
    ("security-faq", "Security FAQ", "SAML SSO and SCIM provisioning are included on Enterprise plans. Data is encrypted in transit and at rest. Regional hosting follows the region selected on the account."),
    ("product-docs", "Product documentation", "Workspace admins manage seats, SSO, billing and API tokens in the AcmeCloud console. Members can view dashboards but cannot change billing settings. Usage dashboards update approximately every hour."),
]


def seed(db: Session, settings: Settings | None = None) -> None:
    for slug, name, plan, region in TENANTS:
        if db.get(Tenant, slug):
            continue
        db.add(Tenant(id=slug, name=name))
        db.flush()
        db.add(Customer(id=f"{slug}-customer", tenant_id=slug, name="Acme Corp" if slug == "demo" else name, email=f"admin@{slug}.example", plan=plan, region=region))
        db.flush()
        db.add(Invoice(id=f"inv-{slug}-mar", tenant_id=slug, customer_id=f"{slug}-customer", amount=549.00, currency="USD", status="paid", billing_period="2026-03", line_items=[{"description": "Enterprise subscription" if plan == "Enterprise" else "Business subscription", "amount": 449.00}, {"description": "Metered API usage", "amount": 100.00}]))
        db.add(Invoice(id=f"inv-{slug}-apr", tenant_id=slug, customer_id=f"{slug}-customer", amount=629.00, currency="USD", status="paid", billing_period="2026-04", line_items=[{"description": "Enterprise subscription" if plan == "Enterprise" else "Business subscription", "amount": 449.00}, {"description": "Metered API usage", "amount": 180.00}]))
    for doc_id, title, content in DOCS:
        if not db.get(KnowledgeDoc, doc_id):
            db.add(KnowledgeDoc(id=doc_id, title=title, content=content))
    if settings and settings.demo_mode:
        db.flush()
        operator = db.scalar(select(Operator).where(Operator.tenant_id == "demo", Operator.email == settings.demo_operator_email))
        if not operator:
            db.add(Operator(tenant_id="demo", email=settings.demo_operator_email, name="Demo Agent", role="admin", password_hash=hash_password(settings.demo_operator_password)))
        elif not verify_password(settings.demo_operator_password, operator.password_hash):
            operator.password_hash = hash_password(settings.demo_operator_password)
    db.commit()
