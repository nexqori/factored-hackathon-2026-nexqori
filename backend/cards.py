"""Local fixture issuer boundary. These values cannot authorize any payment.

Never replace this with dataset PAN/CVV storage. A real issuer integration must
provide its own secure reveal, authentication and dynamic CVV lifecycle.
"""
import secrets
import time
from datetime import datetime, timezone
from fastapi import HTTPException

def reveal_local_card(profile):
    if profile.provider_ref != "local-card-01":
        raise HTTPException(503, "card_unavailable")
    current = datetime.now(timezone.utc)
    if (profile.expiry_year, profile.expiry_month) < (current.year, current.month):
        raise HTTPException(409, "card_expired")
    return {"number": "0000000000008942", "cvv": f"{secrets.randbelow(1000):03d}",
            "expiresAt": int(time.time()) + 60}
