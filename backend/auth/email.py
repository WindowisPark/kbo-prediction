"""이메일 발송 — Resend API."""
import os
import random
import logging
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "KBO AI Analyzer <noreply@kbo-analyzer.com>")
VERIFICATION_EXPIRE_MINUTES = 10


def generate_code() -> str:
    """6자리 인증 코드 생성."""
    return f"{random.randint(0, 999999):06d}"


def get_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)


def send_verification_email(to_email: str, code: str) -> bool:
    """Resend API로 인증 코드 이메일 발송. 성공 시 True."""
    if not RESEND_API_KEY:
        # API 키 없으면 로그만 남기고 성공 처리 (개발 환경)
        logger.warning(f"RESEND_API_KEY not set — verification code for {to_email}: {code}")
        return True

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "[KBO AI Analyzer] 이메일 인증 코드",
                "html": f"""
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
                    <h2 style="color: #1a1a2e;">KBO AI Analyzer</h2>
                    <p>이메일 인증을 완료하려면 아래 코드를 입력해 주세요.</p>
                    <div style="background: #f0f4ff; border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0;">
                        <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #2563eb;">{code}</span>
                    </div>
                    <p style="color: #666; font-size: 14px;">
                        이 코드는 {VERIFICATION_EXPIRE_MINUTES}분간 유효합니다.<br>
                        본인이 요청하지 않았다면 이 이메일을 무시해 주세요.
                    </p>
                </div>
                """,
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info(f"Verification email sent to {to_email}")
            return True
        else:
            logger.error(f"Resend API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False
