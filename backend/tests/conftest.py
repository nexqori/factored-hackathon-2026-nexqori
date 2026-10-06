"""Provider-free default. Jev guard behavior has dedicated contract tests."""
import pytest

@pytest.fixture(autouse=True)
def mock_prompt_guard(monkeypatch):
    from backend import workflow_chat, voice
    monkeypatch.setattr(workflow_chat, 'inspect_prompt', lambda *a, **k: {'status':'allowed'})
    monkeypatch.setattr(voice, 'inspect_prompt', lambda *a, **k: {'status':'allowed'})

    monkeypatch.setattr(voice, 'classify_action', lambda *a, **k: 'continue')
