"""결제 라우터 — Stripe Checkout + Webhook."""
import os
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db, get_current_user
from backend.auth.models import User

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASIC_PRICE_ID = os.getenv("STRIPE_BASIC_PRICE_ID", "")
PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

router = APIRouter(prefix="/payments", tags=["payments"])


# --- Schemas ---

class CheckoutRequest(BaseModel):
    tier: str  # "basic" or "pro"


# --- Helpers ---

TIER_PRICE_MAP = {
    "basic": lambda: BASIC_PRICE_ID,
    "pro": lambda: PRO_PRICE_ID,
}


def _get_or_create_customer(user: User, db: Session) -> str:
    """Stripe Customer 조회 또는 생성."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# --- Endpoints ---

@router.post("/create-checkout")
def create_checkout(req: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Stripe Checkout Session 생성 → 프론트에서 리다이렉트."""
    if not stripe.api_key:
        raise HTTPException(503, "결제 시스템이 준비 중입니다")

    if req.tier not in TIER_PRICE_MAP:
        raise HTTPException(400, "Invalid tier")

    price_id = TIER_PRICE_MAP[req.tier]()
    if not price_id:
        raise HTTPException(503, "가격 정보가 설정되지 않았습니다")

    customer_id = _get_or_create_customer(user, db)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{FRONTEND_URL}/mypage?payment=success",
        cancel_url=f"{FRONTEND_URL}/mypage?payment=cancel",
        metadata={"user_id": str(user.id), "tier": req.tier},
    )

    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe Webhook — 결제 이벤트 처리."""
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(body, sig, WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data, db)

    return JSONResponse({"status": "ok"})


def _handle_checkout_completed(session, db: Session):
    """결제 완료 → 티어 업그레이드."""
    metadata = session.metadata
    logger.info(f"Webhook metadata: {metadata}, type: {type(metadata)}")

    user_id = metadata.get("user_id") if hasattr(metadata, "get") else metadata["user_id"]
    tier = metadata.get("tier") if hasattr(metadata, "get") else metadata["tier"]
    subscription_id = session.subscription

    logger.info(f"Webhook parsed: user_id={user_id}, tier={tier}, sub={subscription_id}")

    if not user_id or not tier:
        logger.warning(f"Checkout completed but missing metadata: {session.id}")
        return

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        # user_id로 못 찾으면 customer_id로 시도
        customer_id = session.customer
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        logger.warning(f"User id={user_id} not found, customer lookup: {user}")

    if not user:
        logger.warning(f"User not found for checkout {session.id}")
        return

    user.tier = tier
    user.stripe_subscription_id = subscription_id
    db.commit()
    logger.info(f"User {user.email} upgraded to {tier}")


def _handle_subscription_updated(subscription, db: Session):
    """구독 변경 (업/다운그레이드)."""
    customer_id = getattr(subscription, "customer", None)
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    # 구독 상태 확인
    status = getattr(subscription, "status", None)
    if status in ("active", "trialing"):
        # price_id로 티어 판별
        items_obj = getattr(subscription, "items", None)
        items = getattr(items_obj, "data", []) if items_obj else []
        if items:
            price = getattr(items[0], "price", None)
            price_id = getattr(price, "id", None) if price else None
            if price_id == BASIC_PRICE_ID:
                user.tier = "basic"
            elif price_id == PRO_PRICE_ID:
                user.tier = "pro"
    elif status in ("canceled", "unpaid", "past_due"):
        user.tier = "free"
        user.stripe_subscription_id = None

    db.commit()


def _handle_subscription_deleted(subscription, db: Session):
    """구독 취소/만료 → Free로 다운그레이드."""
    customer_id = getattr(subscription, "customer", None)
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return

    user.tier = "free"
    user.stripe_subscription_id = None
    db.commit()
    logger.info(f"User {user.email} downgraded to free (subscription deleted)")
