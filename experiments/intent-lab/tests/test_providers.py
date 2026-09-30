import json

import httpx
import pytest

from intent_lab import providers, storage
from intent_lab.decision import LABELS


@pytest.fixture
def private_config(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    (tmp_path / "providers.env").write_text("TYPESAFE_API_KEY=testing-placeholder\nJEV_MODEL=jev-1.13.0\n", encoding="utf-8")
    return tmp_path


def response():
    return {"model": "jev-1.13.0", "answers": {"intent": {"type": "choice", "choice": "incorrect-charge", "probabilities": {label: 1 if label == "incorrect-charge" else 0 for label in LABELS}, "confidence": .98}}, "usage": {"input_tokens": 100, "output_tokens": 50}}


def install_transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(providers.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_one_call_no_credentials_in_result_and_no_false_double_validation(private_config, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
        assert request.headers["authorization"] == "Bearer testing-placeholder"
        return httpx.Response(200, json=response())
    install_transport(monkeypatch, handler)
    result = providers.classify([{"role": "user", "content": "Me cobraron dos veces"}], "es", "Classify")
    assert len(calls) == 1
    assert result["jev"]["intent"] == "incorrect-charge"
    assert result["decision"]["status"] == "pending"
    assert result["jev"]["proposal"]["executes_operation"] is False
    assert "testing-placeholder" not in json.dumps(result)
    saved = list((private_config / "runs").glob("*.json"))
    assert len(saved) == 1 and "testing-placeholder" not in saved[0].read_text()


@pytest.mark.parametrize("status,code", [(401, "auth_error"), (429, "rate_limited"), (529, "rate_limited"), (500, "provider_error"), (302, "provider_error")])
def test_sanitized_provider_errors_and_no_retry(private_config, monkeypatch, status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "testing-placeholder"}, headers={"Location": "https://elsewhere.invalid"})
    install_transport(monkeypatch, handler)
    result = providers.classify([{"role": "user", "content": "Hello"}], "en", "Classify")
    assert len(calls) == 1
    assert result["jev"]["error"] == code
    assert "testing-placeholder" not in json.dumps(result)


def test_missing_key_does_not_call_network(private_config, monkeypatch):
    (private_config / "providers.env").write_text("TYPESAFE_API_KEY=\n")
    def handler(request): raise AssertionError("Unexpected call")
    install_transport(monkeypatch, handler)
    assert providers.classify([{"role": "user", "content": "Hello"}], "en", "Classify")["jev"]["error"] == "missing_key"


def test_timeout_and_invalid_response_do_not_propose_actions(private_config, monkeypatch):
    def handler(request): raise httpx.ReadTimeout("private detail")
    install_transport(monkeypatch, handler)
    result = providers.classify([{"role": "user", "content": "Hello"}], "en", "Classify")
    assert result["jev"]["error"] == "timeout" and result["decision"]["action"] is None
