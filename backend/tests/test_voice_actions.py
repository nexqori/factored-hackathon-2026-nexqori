import pytest
from backend.voice_actions import classify_action


@pytest.mark.parametrize('action', ['submit-claim','case-status','end-call','continue'])
def test_accepts_only_typed_actions_from_customer_text(monkeypatch, action):
    from intent_lab import providers
    seen=[]
    def classify(messages, locale, instructions, **kwargs):
        seen.append(messages)
        return {'status':'ok','intent':action,'provider_confidence':.95}, 1
    monkeypatch.setattr(providers,'classify_jev',classify)
    assert classify_action('Customer request without account records','en')==action
    assert seen==[[{'role':'user','content':'Customer request without account records'}]]


@pytest.mark.parametrize('intent,confidence,status', [('approve-refund',.99,'ok'),('submit-claim',.2,'ok'),('end-call',float('nan'),'ok'),('submit-claim',.99,'unavailable')])
def test_uncertain_or_unavailable_model_never_proposes_an_operation(monkeypatch,intent,confidence,status):
    from intent_lab import providers
    monkeypatch.setattr(providers,'classify_jev',lambda *a,**k:({'intent':intent,'provider_confidence':confidence,'status':status},1))
    assert classify_action('customer message','en')=='continue'


def test_review_context_is_explicit_without_sending_bank_records(monkeypatch):
    from intent_lab import providers
    seen=[]
    def classify(messages,locale,instructions,**kwargs):
        seen.append((messages,instructions))
        return {'status':'ok','intent':'submit-claim','provider_confidence':.95},1
    monkeypatch.setattr(providers,'classify_jev',classify)
    assert classify_action('Confirm and send','en',True)=='submit-claim'
    assert seen[0][0]==[{'role':'user','content':'Confirm and send'}]
    assert 'Trusted application state' in seen[0][1]
    assert 'awaiting submission' in seen[0][1]
