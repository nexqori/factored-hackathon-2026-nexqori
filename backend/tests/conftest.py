"""Provider-free default. Jev guard behavior has dedicated contract tests."""
import pytest

@pytest.fixture(autouse=True)
def mock_prompt_guard(monkeypatch):
    from backend import workflow_chat
    monkeypatch.setattr(workflow_chat, 'inspect_prompt', lambda *a, **k: {'status':'allowed'})
