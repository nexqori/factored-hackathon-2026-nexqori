"""Declared experience informs optional help; age never changes permissions."""
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException

def today():
    return datetime.now(timezone(timedelta(hours=-5))).date()

def age_on(birth_date, on=None):
    on = on or today()
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))

def adult_birth_date(value):
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "birth_date")
    age = age_on(result)
    if age < 18:
        raise HTTPException(422, "adult_required")
    if age > 120:
        raise HTTPException(422, "birth_date")
    return result

def experience_view(profile):
    if not profile:
        return None
    age = age_on(profile.birth_date)
    effective = profile.assistance
    if effective == "auto":
        effective = "guided" if profile.digital_experience in ("new", "learning") or profile.banking_experience == "new" else "standard"
    return {"ageBand": "60_plus" if age >= 60 else "50_59" if age >= 50 else "18_49",
            "bankingExperience": profile.banking_experience, "digitalExperience": profile.digital_experience,
            "assistance": profile.assistance, "effectiveAssistance": effective}
