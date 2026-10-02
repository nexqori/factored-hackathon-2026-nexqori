import pytest
from intent_lab.flow_engine import validate_observations


@pytest.mark.parametrize('text',['Me cobraron de más','I was charged too much','Me cobraram a mais'])
def test_vague_overcharge_does_not_supply_expected_amount(text):
    value={'assessment':'continue','observations':[{'field':'difference','message_index':0,'quote':text}]}
    assert validate_observations(value,['difference'],[{'role':'user','content':text}])['observations']==[]


def test_explicit_expected_amount_remains_customer_declaration():
    text='Yo esperaba pagar 300 MXN.'
    value={'assessment':'continue','observations':[{'field':'difference','message_index':0,'quote':text}]}
    assert validate_observations(value,['difference'],[{'role':'user','content':text}])['observations']==value['observations']
