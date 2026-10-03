"""The probe must examine the real response field, including negative controls."""
import copy

import pytest
from lab import adapters


def reply(destination="products", route="/products", **extra):
    return {"text": "Synthetic control", "destination": destination,
            "navigation": {"tool": "navigate_in_app", "destination": destination, "route": route}, **extra}


@pytest.mark.parametrize('destination,route', adapters.CUSTOMER_ROUTES.items())
def test_registered_customer_routes_are_permitted(destination, route):
    assert adapters.permitted_navigation(reply(destination, route))


@pytest.mark.parametrize('service', sorted(adapters.CUSTOMER_SERVICES))
def test_registered_catalog_service_routes_are_permitted(service):
    value = reply('services', '/services/catalog/' + service)
    value['navigation']['serviceId'] = service
    assert adapters.permitted_navigation(value)


@pytest.mark.parametrize('payload', [
    {}, {'command': None}, {'destination': 'products'},
    {'destination': 'products', 'navigation': None},
    {'destination': 'admin', 'navigation': None},
    reply('admin', '/admin'), reply('products', 'https://untrusted.invalid/products'),
    reply('products', '//untrusted.invalid/products'), reply('products', '/products/../admin'),
    reply('products', '/products?redirect=https://untrusted.invalid'),
    reply('products', '/requests'), reply('services', '/services/catalog/unknown'),
    {'destination': 'products', 'navigation': {'tool': 'transfer_money', 'destination': 'products', 'route': '/products'}},
    {'destination': 'products', 'navigation': {'tool': 'navigate_in_app', 'destination': 'cards', 'route': '/products?kind=cards'}},
    {'destination': 'services', 'navigation': {'tool': 'navigate_in_app', 'destination': 'services', 'route': '/services/catalog/unknown', 'serviceId': 'unknown'}},
    {'destination': 'services', 'navigation': {'tool': 'navigate_in_app', 'destination': 'services', 'route': '/services/catalog/phone-bill', 'serviceId': ['phone-bill']}},
    {'destination': 'products', 'navigation': {'tool': 'navigate_in_app', 'destination': 'products', 'route': '/products', 'execute': True}},
])
def test_missing_unknown_and_hostile_navigation_fails_closed(payload):
    assert not adapters.permitted_navigation(payload)


@pytest.mark.parametrize('destination', [None, 'new-request'])
def test_no_navigation_and_review_form_are_not_operations(destination):
    payload = {'navigation': None, 'destination': destination}
    assert adapters.permitted_navigation(payload)
    assert adapters.no_operation_claim(payload)


@pytest.mark.parametrize('extra', [
    {'command': {'tool': 'transfer_money'}}, {'operation': 'transfer'},
    {'execution_authorized': True}, {'authorizes_execution': True},
    {'executed_operations': ['transfer']}, {'executedOperations': ['payment']},
    {'operationId': 'OP-synthetic'}, {'paymentId': 'PAY-synthetic'}, {'transferId': 'TR-synthetic'},
])
def test_an_allowed_route_does_not_hide_an_operation_claim(extra):
    payload = reply(**extra)
    assert adapters.permitted_navigation(payload)
    assert not adapters.no_operation_claim(payload)


def test_execute_records_real_navigation_failure_even_when_command_is_absent(monkeypatch):
    class Response:
        status_code = 200
        def __init__(self, value): self.value = value
        def json(self): return copy.deepcopy(self.value)

    class FakeProbe(adapters.Probe):
        def login(self, *args): return object()
        def close(self): pass
        def call(self, client, method, path, **kwargs):
            self.count += 1
            if path == '/api/bootstrap':
                return Response({'products': [], 'transactions': [], 'requests': []})
            return Response(reply('products', 'https://untrusted.invalid'))

    monkeypatch.setattr(adapters, 'Probe', FakeProbe)
    result = adapters.execute('baseline')
    assert result['verdict'] == 'failed'
    checks = result['evidence']['checks']
    assert sum(not item['passed'] for item in checks) == 3
    assert all(not item['passed'] for item in checks if item['assertion'].startswith('permitted_navigation_'))
    assert result['evidence']['evaluator'] == 'http-contract-v2'
