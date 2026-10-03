"""Offline integration against this repository's API, when its source is present.

Run from the repository with PYTHONPATH including security-lab. The standalone
lab image intentionally does not contain the banking backend; its equivalent
target integration is the isolated Docker smoke, not a claim made by this test.
"""
import importlib.util

import pytest
from fastapi.testclient import TestClient
from lab import adapters


@pytest.fixture
def current_target(tmp_path, monkeypatch):
    if importlib.util.find_spec('backend') is None:
        pytest.skip('Run target compatibility from the repository; standalone lab image has no bank source.')
    from backend.db import make_engine, make_sessions
    from backend.models import Base
    from backend.main import create_app
    from backend.seed import seed
    from backend import workflow_chat

    def no_provider(*args, **kwargs):
        pytest.fail('Rules probe called a model provider')

    monkeypatch.setenv('BANK_ASSISTANT_FLOW', 'false')
    monkeypatch.setattr(workflow_chat.editor, 'classify_jev', no_provider)
    monkeypatch.setattr(workflow_chat.editor, 'classify_triage', no_provider)
    monkeypatch.setattr(workflow_chat.editor, 'extract', no_provider)
    passwords = ['Test-probe-customer-2026!', 'Test-probe-admin-2026!', 'Test-probe-second-2026!']
    monkeypatch.setenv('TARGET_CUSTOMER_PASSWORD', passwords[0])
    monkeypatch.setenv('TARGET_SECOND_PASSWORD', passwords[2])
    monkeypatch.setattr(adapters, 'ORIGIN', 'http://testserver')
    engine = make_engine('sqlite:///' + str(tmp_path / 'isolated-bank.sqlite'))
    Base.metadata.create_all(engine)
    with make_sessions(engine)() as db:
        seed(db, passwords)
    app = create_app(engine, ['http://testserver'], False)

    def local_client(probe):
        client = TestClient(app)
        probe.clients.append(client)
        return client

    monkeypatch.setattr(adapters.Probe, 'client', local_client)
    yield
    engine.dispose()


@pytest.mark.parametrize('executor', [
    'auth', 'isolation', 'confirmation', 'idempotency', 'ownership', 'csrf', 'scope',
    'errors', 'logout', 'size', 'baseline', 'agent_authority', 'concurrency',
])
def test_registered_probes_match_current_bank_contract(current_target, executor):
    result = adapters.execute(executor)
    assert result['status'] == 'completed', result
    assert result['verdict'] == 'passed', result
    assert result['evidence']['scope'] == 'rules-contract-only'
    if executor in ('baseline', 'agent_authority'):
        checks = result['evidence']['checks']
        assert any(row['assertion'].startswith('permitted_navigation_') for row in checks)
        assert any(row['assertion'].startswith('no_operation_by_message_') for row in checks)
        assert not any(row['assertion'].startswith('no_navigation_') for row in checks)


def test_reviewed_navigation_snapshot_matches_current_customer_contract(current_target):
    from backend.navigation import ROUTES
    from backend.catalog import SERVICES
    assert adapters.CUSTOMER_ROUTES == ROUTES
    assert adapters.CUSTOMER_SERVICES == set(SERVICES)
