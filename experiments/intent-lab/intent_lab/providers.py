"""One explicit Jev call per Play. Credentials stay in the local server file."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

import httpx

from . import storage
from .decision import parse_jev, proposed_action, reconcile, request_preview


def configuration():
    path = storage.DATA_DIR / "providers.env"
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in {"TYPESAFE_API_KEY", "JEV_MODEL"}:
                    values[key.strip()] = value.strip().strip("\"'")
    return values


def provider_status():
    configured = bool(configuration().get("TYPESAFE_API_KEY"))
    return {"jev": "configured" if configured else "pending_connection", "llm": "pending_connection"}


def classify(messages, language, instructions):
    settings = configuration()
    key = settings.get("TYPESAFE_API_KEY")
    request = request_preview(messages, language, instructions)["jev"]
    request["model"] = settings.get("JEV_MODEL") or "jev-1.13.0"
    start = time.perf_counter()
    answer = {"status": "error", "error": "missing_key"}
    if key:
        try:
            # Fixed official endpoint, no redirects/retries or user-controlled URLs.
            with httpx.Client(timeout=httpx.Timeout(25, connect=5), follow_redirects=False) as client:
                response = client.post("https://api.typesafe.ai/v1/systemone", headers={"Authorization": f"Bearer {key}"}, json=request)
            if response.status_code == 200:
                raw = response.json()
                answer = parse_jev(raw)
                usage = raw.get("usage", {})
                if any(type(usage.get(name)) is not int or usage[name] < 0 for name in ("input_tokens", "output_tokens")):
                    raise ValueError("Invalid usage")
                answer["usage"] = {name: usage[name] for name in ("input_tokens", "output_tokens")}
                answer["estimated_api_cost_usd"] = usage["input_tokens"] * 0.042 / 1_000_000
                answer["price_basis"] = "USD 0.042/M input tokens, official model docs checked 2026-09-29; estimate, not invoice"
                answer["proposal"] = proposed_action(answer["intent"])
            else:
                answer = {"status": "error", "error": {401: "auth_error", 403: "auth_error", 429: "rate_limited", 529: "rate_limited"}.get(response.status_code, "provider_error")}
        except httpx.TimeoutException:
            answer = {"status": "error", "error": "timeout"}
        except httpx.HTTPError:
            answer = {"status": "error", "error": "connection_error"}
        except (ValueError, KeyError, TypeError):
            answer = {"status": "error", "error": "invalid_response"}
    answer["latency_ms"] = (time.perf_counter() - start) * 1000 if key else None
    llm = {"status": "pending", "error": "provider_not_configured"}
    result = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), "jev": answer, "llm": llm, "decision": reconcile(answer, llm), "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(), "input_sha256": hashlib.sha256(json.dumps(request["state"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    path = storage.DATA_DIR / "runs"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{result['id']}.json").write_text(json.dumps({"request": request, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
