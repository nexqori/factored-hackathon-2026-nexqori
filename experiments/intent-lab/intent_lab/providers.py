"""Explicit provider calls with validated outputs and private local run records."""
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone

import httpx

from . import storage
from .decision import LABELS, parse_jev, parse_llm, proposed_action, reconcile, request_preview
from backend.agent_routing import route_plan


def configuration():
    path = storage.DATA_DIR / "providers.env"
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() in {"TYPESAFE_API_KEY", "JEV_MODEL", "LLM_API_KEY", "LLM_MODEL", "LLM_REASONING_EFFORT"}:
                    values[key.strip()] = value.strip().strip("\"'")
    return values


def provider_status():
    settings = configuration()
    return {name: "configured" if settings.get(key) else "pending_connection" for name, key in [("jev", "TYPESAFE_API_KEY"), ("llm", "LLM_API_KEY")]}


def classify_jev(messages, language, instructions):
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
    return answer, request


def openai_response(context, instructions, schema, name, validate):
    settings = configuration()
    key = settings.get("LLM_API_KEY")
    if not key:
        return {"status": "pending", "error": "provider_not_configured"}
    model = settings.get("LLM_MODEL") or "gpt-6-luna"
    effort = settings.get("LLM_REASONING_EFFORT") or "high"
    start = time.perf_counter()
    answer = {"status": "error", "error": "provider_error"}
    try:
        payload = {"model": model, "reasoning": {"effort": effort}, "store": False,
                   "max_output_tokens": 4096, "instructions": instructions,
                   "input": [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
                   "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}}}
        with httpx.Client(timeout=httpx.Timeout(55, connect=5), follow_redirects=False) as client:
            response = client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, json=payload)
        if response.status_code == 200:
            raw = response.json()
            if raw.get("status") != "completed":
                answer = {"status": "error", "error": "incomplete_response"}
            else:
                content = [c for item in raw.get("output", []) if item.get("type") == "message" for c in item.get("content", [])]
                texts = [c["text"] for c in content if c.get("type") == "output_text"]
                if any(c.get("type") == "refusal" for c in content):
                    answer = {"status": "error", "error": "refusal"}
                elif len(texts) != 1:
                    raise ValueError("Missing output")
                else:
                    answer = validate(json.loads(texts[0]))
                    usage = raw.get("usage", {})
                    if any(type(usage.get(n)) is not int or usage[n] < 0 for n in ("input_tokens", "output_tokens")):
                        raise ValueError("Invalid usage")
                    answer["usage"] = {n: usage[n] for n in ("input_tokens", "output_tokens")}
                    answer["model"] = raw.get("model", model)
        else:
            code = {401: "auth_error", 403: "auth_error", 429: "rate_limited"}.get(response.status_code, "provider_error")
            # Allowlisted error codes only; never expose raw provider text or headers.
            try:
                provider_code = response.json().get("error", {}).get("code")
                if provider_code in {"model_not_found", "insufficient_quota", "unsupported_parameter", "unsupported_value"}:
                    code = provider_code
            except (ValueError, TypeError, AttributeError):
                pass
            answer = {"status": "error", "error": code, "http_status": response.status_code}
    except httpx.TimeoutException:
        answer = {"status": "error", "error": "timeout"}
    except httpx.HTTPError:
        answer = {"status": "error", "error": "connection_error"}
    except (ValueError, KeyError, TypeError, AttributeError):
        answer = {"status": "error", "error": "invalid_response"}
    return {**answer, "requested_model": model, "reasoning_effort": effort, "latency_ms": (time.perf_counter()-start)*1000}


def classify(messages, language, instructions):
    answer, request = classify_jev(messages, language, instructions)
    preview = request_preview(messages, language, instructions)["llm"]
    schema = {"type": "object", "additionalProperties": False, "required": ["intent", "evidence_message_index", "needs_clarification"],
              "properties": {"intent": {"type": "string", "enum": sorted(LABELS)}, "evidence_message_index": {"type": ["integer", "null"]}, "needs_clarification": {"type": "boolean"}}}
    # The independent classification input deliberately excludes Jev's prediction.
    llm = openai_response({"criteria": preview["criteria"], **preview["input"]}, instructions, schema, "banking_intent", lambda value: parse_llm(value, len(messages)))
    result = {"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(), "jev": answer, "llm": llm, "decision": reconcile(answer, llm), "instructions_sha256": hashlib.sha256(instructions.encode()).hexdigest(), "input_sha256": hashlib.sha256(json.dumps(request["state"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
    result['tool_plan'] = route_plan(answer)
    save_run({"request": request, "result": result, "kind": "classification", "actor": "local_operator"})
    return result


def save_run(record):
    path = storage.DATA_DIR / "runs"
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{record['result']['id']}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
