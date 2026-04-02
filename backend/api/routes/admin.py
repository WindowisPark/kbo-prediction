"""관리자 라우터 — 티어 변경 (테스트/내부용)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.auth.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


class SetTierRequest(BaseModel):
    email: str
    tier: str


@router.post("/set-tier")
def set_tier(req: SetTierRequest, db: Session = Depends(get_db)):
    if req.tier not in ("free", "basic", "pro"):
        raise HTTPException(400, "Invalid tier")

    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(404, "User not found")

    user.tier = req.tier
    db.commit()
    return {"status": "ok", "email": req.email, "tier": req.tier}
