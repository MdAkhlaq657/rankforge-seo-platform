from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models import Organization, Subscription, CreditLedger, User
from app.middleware.auth import get_current_user, get_current_org
from app.services.billing import (
    PLANS, create_checkout_session, handle_webhook,
    grant_plan_credits, compute_credit_debit,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def list_plans():
    """Return all available plans with pricing."""
    return [
        {
            "id": plan_id,
            "name": data["name"],
            "price_monthly": data["price_monthly"],
            "crawl_credits": data["crawl_credits"],
            "keyword_credits": data["keyword_credits"],
            "ai_credits": data["ai_credits"],
            "projects": data["projects"],
            "users": data["users"],
        }
        for plan_id, data in PLANS.items()
    ]


@router.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Get current credit balances and recent usage."""
    plan_data = PLANS.get(org.plan, PLANS["starter"])

    result = await db.execute(
        select(CreditLedger)
        .where(CreditLedger.organization_id == org.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(20)
    )
    recent = result.scalars().all()

    return {
        "plan": org.plan,
        "plan_name": plan_data["name"],
        "crawl_credits_remaining": org.crawl_credits,
        "crawl_credits_total": plan_data["crawl_credits"],
        "keyword_credits_remaining": org.keyword_credits,
        "keyword_credits_total": plan_data["keyword_credits"],
        "recent_transactions": [
            {
                "type": t.ledger_type.value,
                "credit_type": t.credit_type,
                "amount": t.amount,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent
        ],
    }


@router.post("/checkout")
async def create_checkout(
    body: dict,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    """Create Stripe checkout session for plan upgrade."""
    plan = body.get("plan", "growth")
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")

    base_url = body.get("base_url", "http://localhost:3000")
    url = await create_checkout_session(
        org_id=str(org.id),
        plan=plan,
        success_url=f"{base_url}/billing?success=1",
        cancel_url=f"{base_url}/billing?cancelled=1",
        customer_email=user.email,
    )

    if not url:
        # Stripe not configured — simulate upgrade immediately for dev
        return {
            "checkout_url": None,
            "message": "Stripe not configured. Set STRIPE_SECRET_KEY to enable real billing.",
            "dev_mode": True,
            "plan": plan,
        }

    return {"checkout_url": url}


@router.post("/dev-upgrade")
async def dev_upgrade_plan(
    body: dict,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Development-only endpoint to switch plans without Stripe."""
    plan = body.get("plan", "growth")
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    await grant_plan_credits(db, str(org.id), plan)
    await db.commit()
    return {"plan": plan, "message": f"Upgraded to {plan} (dev mode)"}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    event = await handle_webhook(payload, stripe_signature or "")

    if not event:
        return {"received": True}

    if event.get("action") == "activate_subscription":
        plan = event.get("plan", "starter")
        org_id = event.get("org_id")
        if org_id:
            await grant_plan_credits(db, org_id, plan)
            import uuid
            sub_result = await db.execute(
                select(Subscription).where(
                    Subscription.organization_id == uuid.UUID(org_id)
                )
            )
            sub = sub_result.scalar_one_or_none()
            if sub:
                sub.stripe_customer_id = event.get("stripe_customer_id")
                sub.stripe_subscription_id = event.get("stripe_subscription_id")
                sub.plan = plan
            else:
                db.add(Subscription(
                    organization_id=uuid.UUID(org_id),
                    stripe_customer_id=event.get("stripe_customer_id"),
                    stripe_subscription_id=event.get("stripe_subscription_id"),
                    plan=plan,
                ))
            await db.commit()

    return {"received": True}
