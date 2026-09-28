import pytest
from backend.presentation import present_message

@pytest.mark.parametrize('previous,current', [
    ('Tu saldo disponible de demo es 24,850.00 MXN. Abrí tus productos para ver el detalle.', 'Tu saldo disponible es 24,850.00 MXN. Abrí tus productos para ver el detalle.'),
    ('Your available demo balance is 100.00 MXN. I opened your products so you can see the details.', 'Your available balance is 100.00 MXN. I opened your products so you can see the details.'),
    ('Seu saldo disponível de demo é 1.000,00 MXN. Abri seus produtos para você consultar os detalhes.', 'Seu saldo disponível é 1.000,00 MXN. Abri seus produtos para você consultar os detalhes.'),
])
def test_previous_canned_copy_keeps_amount_and_user_messages_intact(previous,current):
    assert present_message(previous,'assistant')==current
    assert present_message(previous,'user')==previous

def test_unrecognized_history_is_not_rewritten():
    text='Previous wording provided by a person: demo balance, transfer pending.'
    assert present_message(text,'assistant')==text
