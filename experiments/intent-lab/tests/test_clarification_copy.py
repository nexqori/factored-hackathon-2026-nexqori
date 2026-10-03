import pytest
from intent_lab.workflow_routing import clarification_reply, STANDARD_CLARIFICATION


@pytest.mark.parametrize('language,message,topic', [
    ('es','tengo un problema con una transferencia','transferencia'),
    ('en','I have a problem with a transfer','transfer'),
    ('pt','Tenho um problema com uma transferência','transferência'),
])
def test_problem_asks_for_symptom_not_family(language,message,topic):
    ctx={'triage':{'family':'problem'},'intent':'needs-clarification'}
    reply=clarification_reply(ctx,[{'role':'user','content':message}],language,STANDARD_CLARIFICATION[language])
    assert topic in reply
    assert reply != STANDARD_CLARIFICATION[language]
    assert ctx['intent']=='needs-clarification'  # Copy never selects a contract.


@pytest.mark.parametrize('language',['es','en','pt'])
def test_operator_question_is_preserved(language):
    assert clarification_reply({'triage':{'family':'problem'}},[],language,'My configured question')=='My configured question'


def test_negated_transfer_and_multiple_topics_do_not_assume_a_transfer_failure():
    ctx={'triage':{'family':'problem'},'intent':'needs-clarification'}
    assert 'transferencia' not in clarification_reply(ctx,[{'role':'user','content':'No es una transferencia, es algo de la tarjeta'}],'es',STANDARD_CLARIFICATION['es'])
    ctx['intent']='multiple-intents'
    assert 'primero' in clarification_reply(ctx,[],'es',STANDARD_CLARIFICATION['es'])
