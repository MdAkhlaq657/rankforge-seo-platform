"""
Stripe billing service.
Handles subscription creation, webhooks, and credit top-ups.
"""
from datetime import datetime, timezone
from typing import Optional
import structlog

from app.config import settings

logger = structlog.get_logger()

PLANS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 49,
        "crawl_credits": 5_000,
        "keyword_credits": 500,
        "ai_credits": 10,
        "projects": 3,
        "users": 2,
        "stripe_price_id": "",  # set in env
    },
    "growth": {
        "name": "Growth",
        "price_monthly": 149,
        "crawl_credits": 50_000,
        "keyword_credits": 5_000,
        "ai_credits": 50,
        "projects": 10,
        "users": 5,
        "stripe_price_id": "",
    },
    "agency": {
        "name": "Agency",
        "price_monthly": 399,
        "crawl_credits": 500_000,
        "keyword_credits": 50_000,
        "ai_credits": 200,
        "projects": -1,   # unlimited
        "users": 20,
        "stripe_price_id": "",
    },
}

CREDIT_COSTS = {
    "crawl":   {"per": 100, "credits": 1},     # 1 credit per 100 pages
    "keyword": {"per": 10,  "credits": 1},     # 1 credit per 10 lookups
    "ai":      {"per": 1,   "credits": 5},     # 5 credits per AI brief
    "report":  {"per": 1,   "credits": 2},     # 2 credits per report
}

try:
    import stripe
    stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
    STRIPE_AVAILABLE = bool(getattr(settings, "STRIPE_SECRET_KEY", ""))
except ImportError:
    STRIPE_AVAILABLE = False


async def create_checkout_session(
    org_id: str,
    plan: str,
    success_url: str,
    cancel_url: str,
    customer_email: Optional[str] = None,
) -> Optional[str]:
    """Create Stripe checkout session. Returns URL."""
    if not STRIPE_AVAILABLE:
        return None
    plan_data = PLANS.get(plan)
    if not plan_data or not plan_data["stripe_price_id"]:
        return None
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": plan_data["stripe_price_id"], "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=customer_email,
            metadata={"org_id": org_id, "plan": plan},
        )
        return session.url
    except Exception as e:
        logger.error("Stripe checkout failed", error=str(e))
        return None


async def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Process Stripe webhook events."""
    if not STRIPE_AVAILABLE:
        return {}
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        logger.error("Webhook construction failed", error=str(e))
        return {}

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        return {
            "action": "activate_subscription",
            "org_id": data.get("metadata", {}).get("org_id"),
            "plan": data.get("metadata", {}).get("plan"),
            "stripe_customer_id": data.get("customer"),
            "stripe_subscription_id": data.get("subscription"),
        }
    elif event_type == "customer.subscription.deleted":
        return {
            "action": "cancel_subscription",
            "stripe_subscription_id": data.get("id"),
        }
    return {}


def compute_credit_debit(action: str, quantity: int = 1) -> int:
    """Return number of credits to debit for a given action."""
    cost_def = CREDIT_COSTS.get(action)
    if not cost_def:
        return 0
    return math.ceil(quantity / cost_def["per"]) * cost_def["credits"]


import math


async def debit_credits(
    db,
    org_id: str,
    credit_type: str,
    amount: int,
    description: str,
    reference_id: Optional[str] = None,
) -> bool:
    """
    Debit credits from org. Returns False if insufficient.
    Updates org.crawl_credits or org.keyword_credits in-place.
    """
    from sqlalchemy import select
    from app.models import Organization, CreditLedger, CreditLedgerType
    import uuid

    result = await db.execute(
        select(Organization).where(Organization.id == uuid.UUID(org_id))
    )
    org = result.scalar_one_or_none()
    if not org:
        return False

    if credit_type == "crawl":
        if org.crawl_credits < amount: return False
        org.crawl_credits -= amount
    elif credit_type in ("keyword", "ai", "report"):
        if org.keyword_credits < amount: return False
        org.keyword_credits -= amount
    else:
        return False

    ledger_entry = CreditLedger(
        organization_id=uuid.UUID(org_id),
        ledger_type=CreditLedgerType.DEBIT,
        credit_type=credit_type,
        amount=-amount,
        description=description,
        reference_id=reference_id,
    )
    db.add(ledger_entry)
    await db.flush()
    return True


async def grant_plan_credits(db, org_id: str, plan: str) -> None:
    """Grant monthly credits for a plan. Called on subscription activation."""
    from app.models import Organization, CreditLedger, CreditLedgerType
    from sqlalchemy import select
    import uuid

    plan_data = PLANS.get(plan, PLANS["starter"])
    result = await db.execute(
        select(Organization).where(Organization.id == uuid.UUID(org_id))
    )
    org = result.scalar_one_or_none()
    if not org:
        return

    org.plan = plan
    org.crawl_credits = plan_data["crawl_credits"]
    org.keyword_credits = plan_data["keyword_credits"]

    db.add(CreditLedger(
        organization_id=uuid.UUID(org_id),
        ledger_type=CreditLedgerType.GRANT,
        credit_type="crawl",
        amount=plan_data["crawl_credits"],
        description=f"Monthly credits — {plan_data['name']} plan",
    ))
    db.add(CreditLedger(
        organization_id=uuid.UUID(org_id),
        ledger_type=CreditLedgerType.GRANT,
        credit_type="keyword",
        amount=plan_data["keyword_credits"],
        description=f"Monthly credits — {plan_data['name']} plan",
    ))
    await db.flush()
