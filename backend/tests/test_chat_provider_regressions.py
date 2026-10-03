"""Regresiones de fallos encontrados durante la batería privada de 100 casos."""
import copy
import pytest
from backend.chat_gateway import ChatGateway  # Hace disponible el paquete independiente.
from nexqori_chat.proveedores import Providers
from nexqori_chat.config import Settings
from nexqori_chat.contratos import Trace,AgentError,Conversation
from nexqori_chat.codigo5_rag import responder_rag

@pytest.mark.parametrize('values,accepted',[
 ({'a':.68,'b':.19,'c':.11,'d':.01,'e':0},True),
 ({'a':.7,'b':.2,'c':.11,'d':0,'e':0},True),
 ({'a':.6,'b':.2,'c':.1,'d':0,'e':0},False),
 ({'a':0,'b':0,'c':0,'d':0,'e':0},False),
 ({'a':.6811,'b':.19,'c':.11,'d':.01,'e':0},False),
])
def test_bounded_jev_rounding_preserves_original(values,accepted,monkeypatch):
    trace=Trace();p=Providers(Settings(),trace)
    original=copy.deepcopy(values)
    data={'answers':{'decision':{'type':'choice','probabilities':values,'choice':'a','confidence':.6}}}
    monkeypatch.setattr(p,'_post',lambda *args:data)
    if accepted:
        result=p.choice('test',{},'elige',{k:k for k in values})
        assert sum(result['probabilities'].values())==pytest.approx(1)
        assert result['raw_probabilities']==original and values==original
        assert result['label']=='a' and result['confidence']==.6
        assert any(e.get('normalization')=='bounded_rounding' for e in trace.events)
    else:
        with pytest.raises(AgentError,match='Distribución no normalizada'):p.choice('test',{},'elige',{k:k for k in values})

@pytest.mark.parametrize('facts,citations,answer,accepted',[
 ([],[],'La consulta no devolvió solicitudes.',True),
 ([],['F1'],'No hay solicitudes [F1].',False),
 ([],[],'No hay solicitudes [F1].',False),
 ([{'fact_id':'F2'}],['F2'],'Dato [F2].',True),
 ([{'fact_id':'F2'}],['F1'],'Dato [F1].',False),
])
def test_rag_citations_bound_to_actual_sources(facts,citations,answer,accepted):
    class Repo:
        def retrieve(self,*args):return {'status':'ok','facts':facts}
    class Fake:
        def generate(self,stage,state,instructions,schema):
            if facts: assert schema['properties']['citations']['items']['enum']==['F2']
            else: assert schema['properties']['citations']['maxItems']==0
            return {'answer':answer,'citations':citations,'operations_executed':False}
    conv=Conversation('test','test');conv.messages=[{'role':'user','text':'consulta','language':'es','timestamp':'2026-10-02T00:00:00Z'}]
    call=lambda:responder_rag(conv,'requests',{}, {},{},'fake',Repo(),Fake(),Trace())
    if accepted:assert call()['status']=='answered'
    else:
        with pytest.raises(AgentError):call()
