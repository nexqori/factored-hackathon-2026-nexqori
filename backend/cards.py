"""Local fixture issuer boundary. These values cannot authorize any payment.

Never replace this with dataset PAN/CVV storage. A real issuer integration must
provide its own secure reveal, authentication and dynamic CVV lifecycle.
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone
from fastapi import HTTPException

def local_card_available(profile):
    return bool(profile and (profile.provider_ref == 'local-card-01' or profile.provider_ref == profile.product_id or profile.provider_ref.startswith('verify-card-')))


def signature(profile, secret, expires):
    return hmac.new(secret.encode(), f'local-card-reveal:{profile.user_id}:{profile.product_id}:{expires}'.encode(), hashlib.sha256).hexdigest()


def local_cvv(profile, secret, stamp):
    window = stamp // 900
    code = hmac.new(secret.encode(), f'local-card-cvv:{profile.provider_ref}:{window}'.encode(), hashlib.sha256).digest()
    # Separate even/odd windows so adjacent values always differ.
    return {'cvv': f'{(int.from_bytes(code[:4], "big") % 500) * 2 + window % 2:03d}',
            'cvvExpiresAt': (window + 1) * 900, 'serverTime': stamp}


def validate_local_card(profile):
    if not local_card_available(profile): raise HTTPException(503, 'card_unavailable')
    current = datetime.now(timezone.utc)
    if (profile.expiry_year, profile.expiry_month) < (current.year, current.month):
        raise HTTPException(409, "card_expired")


def reveal_local_card(profile, last4, secret):
    validate_local_card(profile)
    stamp = int(time.time()); expires = stamp + 60
    # Preserve the original fixture; other local cards use a non-issuer prefix.
    # No real PAN/CVV is stored or imported.
    number = '4000056655665556' if profile.provider_ref == 'local-card-01' else '999999' + f'{int(hashlib.sha256(profile.provider_ref.encode()).hexdigest()[:12],16)%1000000:06d}' + last4
    return {'number': number, 'expiryMonth': profile.expiry_month, 'expiryYear': profile.expiry_year,
            'expiresAt': expires, 'revealToken': f'{expires}.{signature(profile, secret, expires)}', **local_cvv(profile, secret, stamp)}


def refresh_local_cvv(profile, secret, token):
    validate_local_card(profile)
    try: raw, supplied = token.split('.', 1); expires = int(raw)
    except (ValueError, AttributeError): raise HTTPException(403, 'card_password') from None
    stamp = int(time.time())
    if not stamp < expires <= stamp + 60 or not hmac.compare_digest(supplied, signature(profile, secret, expires)):
        raise HTTPException(403, 'card_password')
    return local_cvv(profile, secret, stamp)
