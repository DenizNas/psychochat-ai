from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from src.services.database import SessionLocal, UserSubscription, SubscriptionPlan, SubscriptionStatus
from src.services.auth import get_current_user

# TODO: Implement basic free daily chat limit for non-premium users in Phase 10E.8D.
# Limit: 5 AI messages per rolling 24h. Premium/professional users unlimited.
# Crisis exception: Run crisis detection before enforcing chat limit. If crisis is detected, always bypass limit.

class AccessDeniedResponse(BaseModel):
    detail: str
    error_code: str
    required_tier: str

def get_user_subscription_tier(username: str, db) -> str:
    """
    Queries database to resolve user's subscription tier: 'free', 'premium', or 'professional_support'.
    """
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == username,
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).first()
    if not sub:
        return "free"
    
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    if not plan:
        return "free"
    
    plan_name = plan.name.lower()
    if plan_name in ["premium", "professional_support"]:
        return plan_name
    return "free"

def is_premium_or_higher(username: str, db) -> bool:
    """
    Checks if user is premium or higher tier.
    """
    tier = get_user_subscription_tier(username, db)
    return tier in ["premium", "professional_support"]

def require_premium_user(username: str = Depends(get_current_user)) -> str:
    """
    FastAPI dependency that enforces the user has premium or higher subscription status.
    Raises HTTP 403 Forbidden with structured metadata on failure.
    """
    db = SessionLocal()
    try:
        if not is_premium_or_higher(username, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "detail": "Bu özellik yalnızca Premium üyeler içindir.",
                    "error_code": "PREMIUM_MEMBER_REQUIRED",
                    "required_tier": "premium"
                }
            )
        return username
    finally:
        db.close()
