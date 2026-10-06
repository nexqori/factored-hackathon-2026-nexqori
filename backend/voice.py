"""Optional, single-process GPT-Live host. Audio never passes through the bank.

Only trusted sideband events can delegate. Browser requests select an owned
conversation, keep a lease alive or close it; they cannot submit tool results.
"""
import copy
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from .models import VoiceSession, Session, Conversation, ConversationFlow, User, RequestCase, AuditEvent, Message, now
from .security import customer, customer_read, current_session, db_session
from .schemas import StrictModel, Locale
from .transaction_context import transaction_evidence
from .workflow_chat import FlowMessage, RegisterClaim, register_reviewed_claim, run_chat_turn, flow_view, enabled as flow_enabled, next_message_time
from .voice_actions import classify_action
from .claim_summary import preview_token
from .prompt_guard import inspect_prompt
from .voice_summary import presentation
from .conversation_closed import require_open
from .navigation import navigate_in_app
from .voice_provider import LiveProvider, VOICES, enabled, api_key, send, opening_instructions

ACTIVE = ('connecting','active','closing')
LIMIT_SECONDS = 300
LEASE_SECONDS = 45


class StartVoice(StrictModel):
    requestKey: str = Field(pattern=r'^[a-zA-Z0-9-]{16,64}$')
    conversationId: str | None = Field(default=None, max_length=64)
    transactionId: str | None = Field(default=None, max_length=64)
    requestId: str | None = Field(default=None, max_length=64)
    locale: Locale
    voice: Literal['marin','cedar','coral','bossa','tempo'] = 'marin'
    sdp: str = Field(min_length=4, max_length=60000)


def view(row):
    return {'id':row.id,'conversationId':row.conversation_id,'status':row.status,
        'expiresAt':row.expires_at,'revision':row.state.get('revision',0),
        'reply':row.state.get('reply'),'reason':row.state.get('reason'),
        'remoteClosed':row.state.get('remote_closed',False)}


def audit(db, row, action):
    db.add(AuditEvent(id=str(uuid4()),user_id=row.user_id,actor_id=row.user_id,
                     conversation_id=row.conversation_id,action=action))


def disconnect(socket):
    # A transport cleanup failure must not skip the persisted close result.
    try: socket.close()
    except Exception: pass


def safe_spoken_result(reply, locale, verified_presentation=None):
    """Only deterministic bank presentation, never arbitrary model reply text."""
    if verified_presentation:
        return verified_presentation['summary']
    flow = reply.get('flow') or {}
    i=('es','en','pt').index(locale)
    if flow.get('state')=='provider_unavailable':
        return ('No pude completar la revisión en este momento. Tu conversación y el movimiento elegido se conservan. Puedes pedirme que lo intente de nuevo.',
                'I could not finish the review right now. Your conversation and selected transaction are preserved. You can ask me to try again.',
                'Não consegui concluir a análise agora. Sua conversa e a movimentação escolhida foram preservadas. Pode pedir que eu tente novamente.')[i]
    search=flow.get('transactionSearch') or {}
    if flow.get('suggestedTransaction'):
        return ('Encontré un movimiento posible y lo estoy mostrando en Movimientos y en el panel de la llamada. ¿Es ese el que quieres revisar? Puedes decir sí o no.',
                'I found a possible transaction and am showing it in Transactions and the call panel. Is that the one you want to review? You can say yes or no.',
                'Encontrei uma possível movimentação e estou mostrando em Movimentações e no painel da chamada. É essa que você quer revisar? Pode dizer sim ou não.')[i]
    if search.get('kind')=='browse':
        return ('Voy a mostrar tus movimientos en pantalla. Seguimos con el mismo problema. Dime cuál quieres revisar por el comercio o la referencia que ves.',
                'I will show your transactions on screen. We are continuing the same issue. Tell me which one to review using the merchant or reference you see.',
                'Vou mostrar suas movimentações na tela. Continuamos com o mesmo problema. Diga qual quer revisar pelo estabelecimento ou pela referência que vê.')[i]
    if search.get('kind')=='no_match':
        return ('No encontré un movimiento que coincida con esas pistas. ¿Recuerdas el comercio o prefieres que muestre todos tus movimientos? No necesitas darme todos los datos.',
                'I found no transaction matching those clues. Do you remember the merchant, or would you prefer to see all your transactions? You do not need to provide every detail.',
                'Não encontrei uma movimentação com essas informações. Lembra do estabelecimento ou prefere ver todas as movimentações? Não precisa informar todos os dados.')[i]
    # Known field names select fixed questions. Never relay model-generated
    # questions or bank-enriched reply text to the external speech model.
    questions={
        'difference':('¿Qué importe esperabas pagar?', 'What amount did you expect to pay?', 'Qual valor você esperava pagar?'),
        'date':('¿En qué fecha ocurrió?', 'On what date did it happen?', 'Em que data aconteceu?'),
        'transaction_id':('Puedo buscar el movimiento por ti. Dime el comercio o el importe que recuerdas.', 'I can look up the transaction for you. Tell me the merchant or the amount you remember.', 'Posso buscar a movimentação para você. Diga o estabelecimento ou o valor que lembra.'),
        'request_id':('Puedes abrir Mis reclamos para elegir el expediente sin terminar la llamada.', 'You can open My complaints to choose the case without ending the call.', 'Pode abrir Minhas reclamações para escolher o protocolo sem encerrar a chamada.')}
    missing=flow.get('missing_fields') or []
    # Selecting a record can supply its date and amount. Ask that first rather
    # than demanding fields already available in the authenticated bank.
    field='transaction_id' if 'transaction_id' in missing else missing[0] if missing else None
    if field in questions:return questions[field][i]
    key = 'review' if flow.get('canRegister') else 'question' if flow.get('missing_fields') else 'screen'
    messages = {
        'review':('Reuní los datos para solicitar revisión de un supervisor. Puedes revisar y confirmar el reclamo aquí sin terminar la llamada.',
            'I gathered the details for supervisor review. You can review and confirm the complaint here without ending the call.',
            'Reuni os dados para análise de um supervisor. Pode revisar e confirmar a reclamação aqui sem encerrar a chamada.'),
        'question':('Necesito aclarar qué ocurrió y qué resultado esperabas. Cuéntamelo y continuamos.',
            'I need to clarify what happened and what outcome you expected. Tell me so we can continue.',
            'Preciso esclarecer o que aconteceu e qual resultado esperava. Conte para continuarmos.'),
        'screen':('Entiendo que hay un problema. ¿El importe es mayor al esperado, no reconoces el pago o no se completó?',
            'I understand there is a problem. Is the amount higher than expected, is it unfamiliar, or did the payment not complete?',
            'Entendo que há um problema. O valor é maior que o esperado, não reconhece o pagamento ou ele não foi concluído?')}
    return messages[key][('es','en','pt').index(locale)]


def sent_farewell(case_id, locale):
    return (
        f'Tu reclamo {case_id} quedó enviado. Ya puedes verlo en Mis reclamos. Gracias por avisarnos; que tengas un buen día.',
        f'Your complaint {case_id} was submitted. You can now see it in My complaints. Thank you for letting us know. Have a good day.',
        f'Sua reclamação {case_id} foi enviada. Já pode vê-la em Minhas reclamações. Obrigado por avisar. Tenha um bom dia.'
    )[('es','en','pt').index(locale)]


class TranscriptBuffer:
    """Keep complete fragments in order; never classify every partial caption."""
    def __init__(self):
        self.fragments = []; self.ids = set(); self.used = set()

    def add(self, event):
        identity = event.get('event_id'); delta = event.get('delta')
        start, end = event.get('start_ms'), event.get('end_ms')
        if not isinstance(identity,str) or identity in self.ids: return
        if not isinstance(delta,str) or not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or not 0 <= start <= end: return
        if len(self.ids)>=2000 or sum(len(f['delta']) for f in self.fragments)+len(delta)>32000:
            raise ValueError('voice_transcript_limit')
        self.ids.add(identity); self.fragments.append(dict(event))

    def take(self, offset):
        # A delegation can land inside the last word's timestamp span. Keep
        # that whole fragment; otherwise its suffix leaks into the next turn.
        chosen = sorted((f for f in self.fragments if f['event_id'] not in self.used and f['start_ms']<=offset),
                        key=lambda f:(f['start_ms'],f['end_ms']))
        # Late fragments from a previous utterance must not prefix a new reply.
        # Acoustic separation, not matching particular confirmation words.
        start = 0
        for index in range(1, len(chosen)):
            if chosen[index]['start_ms'] - chosen[index-1]['end_ms'] > 2500:
                start = index
        text = ''.join(f['delta'] for f in chosen[start:]).strip()
        if len(text)>8000: raise ValueError('voice_transcript_limit')
        self.used.update(f['event_id'] for f in chosen)
        return text


class VoiceRuntime:
    def __init__(self, sessions, conversation_view, message_view, provider=None):
        self.sessions = sessions; self.conversation_view = conversation_view; self.message_view = message_view
        self.provider = provider or LiveProvider(); self.lock = threading.Lock(); self.jobs = {}

    def live(self, identity):
        with self.sessions() as db:
            row = db.get(VoiceSession,identity)
            if not row or row.status not in ACTIVE or not enabled(): return False
            auth = db.get(Session,row.auth_hash); user = db.get(User,row.user_id)
            stamp = int(time.time())
            return bool(auth and auth.user_id==row.user_id and auth.expires_at>stamp and user and user.role=='customer'
                        and row.expires_at>stamp and row.heartbeat_at+LEASE_SECONDS>stamp)

    def update(self, identity, status=None, **fields):
        with self.sessions() as db:
            row=db.scalar(select(VoiceSession).where(VoiceSession.id==identity).with_for_update())
            if not row:return
            if status: row.status=status
            row.state={**row.state,**fields}; db.commit()

    def turn(self, identity, delegation_id, text):
        with self.sessions() as db:
            row=db.get(VoiceSession,identity)
            if not row or not self.live(identity): raise RuntimeError('voice_session_ended')
            user=db.scalar(select(User).where(User.id==row.user_id).with_for_update())
            # Revalidate after obtaining the same owner lock as the text flow.
            if not self.live(identity): raise RuntimeError('voice_session_ended')
            conv=db.get(Conversation,row.conversation_id)
            flow=db.get(ConversationFlow,conv.id)
            selected_request=(flow.state.get('bank_binding',{}).get('request_id') if flow else row.state.get('request_id'))
            key=hashlib.sha256((identity+':'+delegation_id).encode()).hexdigest()
            shown = flow.state.get('shown_claim') if flow else None
            receipt = (row.state.get('delegations') or {}).get(delegation_id)
            if receipt:
                previous = row.state.get('reply') or {}
                return safe_spoken_result(previous, row.locale, previous.get('voiceSummary'))
            awaiting_claim = bool(flow and not flow.request_id and shown and shown.get('ready')
                and shown.get('locale') == row.locale
                and 0 <= now().timestamp() - shown.get('at', 0) < 600
                and shown.get('token') == preview_token(conv, flow.state, row.locale))
            action = classify_action(text, row.locale, awaiting_claim)
            # Ending media is not a bank operation. A banking content guard
            # must never trap a customer in a billed call they asked to end.
            if action == 'end-call':
                farewell = ('Gracias por llamar. Que tengas un buen día.', 'Thank you for calling. Have a good day.',
                            'Obrigado por ligar. Tenha um bom dia.')[('es','en','pt').index(row.locale)]
                row.state = {**row.state, 'end_requested': True, 'last_action':action}
                audit(db, row, 'voice_end_requested'); db.commit()
                return farewell
            if action in ('case-status','open-complaints','show-refund') and flow and flow.request_id:
                selected_request = flow.request_id
            elif action in ('case-status','open-complaints','show-refund') and not selected_request:
                from .case_followup import unique_owned_claim
                selected_request = unique_owned_claim(db, user.id)
            can_submit = action == 'submit-claim' and awaiting_claim
            if can_submit and inspect_prompt(text, row.locale)['status'] == 'allowed':
                require_open(db, conv)
                spoken = Message(id=str(uuid4()), user_id=user.id, conversation_id=conv.id,
                    role='user', content=text, locale=row.locale, created_at=next_message_time(db,conv,user))
                db.add(spoken); db.flush()
                claim = register_reviewed_claim(conv.id, RegisterClaim(details=shown['details'],
                    confirmed=True, locale=row.locale, previewToken=shown['token'], requestKey=key),
                    user, db, self.message_view)
                reply = {'text':claim['message']['text'], 'conversation':self.conversation_view(conv),
                    'messages':[self.message_view(spoken),claim['message']], 'flow':claim['flow'],
                    'destination':'complaints', 'navigation':navigate_in_app('complaints','customer',case_id=claim['id'])}
            else:
                reply=run_chat_turn(FlowMessage(message=text,locale=row.locale,conversationId=conv.id,
                    transactionId=conv.transaction_id,requestId=selected_request,requestKey=key),
                    user,db,self.conversation_view,self.message_view,
                    navigation_action=action if action in ('open-complaints','show-refund') else None)
            if (reply.get('appCommand') or {}).get('type')=='prepare_profile':
                reply={**reply,'appCommand':None,'destination':'settings','navigation':navigate_in_app('settings','customer')}
            summary=presentation(db,user.id,reply,row.locale)
            # Once the comparison was spoken, subsequent draft turns only state
            # the next action. Corrections still update the form and chart.
            findings_key = json.dumps([conv.transaction_id, (summary or {}).get('comparison')], sort_keys=True)
            if summary and (reply.get('flow') or {}).get('canRegister') and not reply.get('guard'):
                if row.state.get('spoken_findings') == findings_key:
                    summary = {**summary, 'summary': (
                        'El borrador está listo. Puedes corregirlo o decir «confirmar y enviar».',
                        'The draft is ready. You can edit it or say “confirm and send”.',
                        'O rascunho está pronto. Pode corrigir ou dizer “confirmar e enviar”.')[('es','en','pt').index(row.locale)]}
                row.state = {**row.state, 'spoken_findings': findings_key}
            if can_submit and (reply.get('flow') or {}).get('requestId'):
                summary = {**(summary or {}), 'summary': sent_farewell(claim['id'],row.locale)}
                row.state = {**row.state, 'announced_case_id':claim['id']}
            reply={**reply,'voiceSummary':summary}
            # The shared service committed the turn. Its key prevents duplicate
            # messages even if a crash occurs before this receipt is committed.
            db.flush(); db.expire_all(); row=db.scalar(select(VoiceSession).where(VoiceSession.id==identity).with_for_update())
            receipts=dict(row.state.get('delegations',{}))
            if delegation_id not in receipts:
                receipts[delegation_id]=key
                row.state={**row.state,'reply':reply,'revision':row.state.get('revision',0)+1,'delegations':receipts,'last_action':action}
                audit(db,row,'voice_turn');db.commit()
            return safe_spoken_result(reply,row.locale,summary)

    def registration_notice(self, identity):
        with self.sessions() as db:
            row=db.scalar(select(VoiceSession).where(VoiceSession.id==identity).with_for_update())
            if not row or not self.live(identity):return None
            flow=db.get(ConversationFlow,row.conversation_id)
            if not flow or flow.user_id!=row.user_id or not flow.request_id or row.state.get('announced_case_id')==flow.request_id:return None
            case=db.get(RequestCase,flow.request_id)
            if not case or case.user_id!=row.user_id:return None
            conv=db.get(Conversation,row.conversation_id)
            registered=(flow.state.get('claim_registration') or {}).get('response')
            if not registered:return None
            from .case_followup import read_case_status, case_status_navigation
            navigation=case_status_navigation(read_case_status(db,row.user_id,case.id))
            reply={'text':registered['message']['text'], 'conversation':self.conversation_view(conv),
                   'messages':[registered['message']], 'flow':flow_view(flow), 'destination':navigation['destination'],
                   'navigation':navigation}
            summary=presentation(db,row.user_id,reply,row.locale)
            if not summary:return None
            if case.status == 'received':
                summary = {**summary, 'summary':sent_farewell(case.id,row.locale)}
            reply['voiceSummary']=summary
            row.state={**row.state,'reply':reply,'revision':row.state.get('revision',0)+1,'announced_case_id':case.id}
            audit(db,row,'voice_case_registered_notice');db.commit()
            return summary['summary']

    def start(self, identity, socket):
        stop=threading.Event(); ready=threading.Event()
        thread=threading.Thread(target=self.run,args=(identity,socket,stop,ready),daemon=True,name='nexqori-voice')
        with self.lock:
            self.jobs[identity]=(stop,thread)
        thread.start(); ready.wait(3)

    def close(self, identity):
        with self.lock: job=self.jobs.get(identity)
        if job: job[0].set()

    def shutdown(self):
        with self.lock: jobs=list(self.jobs.values())
        for stop,_ in jobs:stop.set()
        for _,thread in jobs:thread.join(timeout=5)

    def recover_one(self, identity):
        """Retry only closure, never creation or a delegated financial action."""
        with self.sessions() as db:
            row=db.get(VoiceSession,identity)
            provider_id=row.provider_id if row else None
        closed=False;socket=None
        try:
            if provider_id:
                socket=self.provider.attach(provider_id);send(socket,'session.close')
                until=time.monotonic()+3
                while time.monotonic()<until:
                    if json.loads(socket.recv(timeout=max(.1,until-time.monotonic()))).get('type')=='session.closed':
                        closed=True;break
        except Exception:pass
        finally:
            if socket:disconnect(socket)
        self.update(identity,'closed' if closed else 'failed',remote_closed=closed,
                    reason='ended' if closed else 'close_unconfirmed',ended_at=int(time.time()))

    def recover(self):
        if not enabled():return
        with self.sessions() as db:
            identities=db.scalars(select(VoiceSession.id).where(VoiceSession.status.in_(ACTIVE))).all()
        for identity in identities:self.recover_one(identity)

    def run(self, identity, socket, stop, ready):
        fragments=TranscriptBuffer(); pending=[]; seen=set(); future=None; work_id=None
        pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='nexqori-voice-turn')
        closed=False; reason='ended'; final_usage=None
        greeting_decided=False; greeting_id=None; greeting_sent_at=None; greeting_acked=False
        speech_started=False; next_case_check=0; ending_at=None; last_output_at=None; last_input_at=0; closing_text=''
        try:
            with self.sessions() as db:
                locale=db.get(VoiceSession,identity).locale
            self.update(identity,'active');ready.set()
            while not stop.is_set() and self.live(identity):
                if greeting_sent_at is not None and not greeting_acked and time.monotonic()-greeting_sent_at>10:
                    self.update(identity,greeting_status='unconfirmed')
                    greeting_sent_at=None  # Never retry speech after an ambiguous acknowledgment.
                if future and future.done():
                    result=future.result()
                    future=None
                    with self.sessions() as db:
                        ending=db.get(VoiceSession,identity).state.get('end_requested')
                    if ending:
                        send(socket,'session.instructions.append',delegation_id=work_id,
                             content='The customer has ended the call. Say this complete farewell now, exactly once: "'+result+'" Do not add an acknowledgment, filler, question or any further information. Then remain silent while the application closes the call.')
                        ending_at=time.monotonic(); last_output_at=None; closing_text=''
                    else:
                        send(socket,'session.commentary.append',delegation_id=work_id,content=result)
                if ending_at is not None and ((last_output_at and len(closing_text.strip())>=12 and time.monotonic()-last_output_at>3 and time.monotonic()-ending_at>5)
                                             or time.monotonic()-ending_at>15):
                    reason='requested_by_customer'; break
                if not future and not pending and time.monotonic()>=next_case_check:
                    next_case_check=time.monotonic()+1
                    notice=self.registration_notice(identity)
                    if notice:send(socket,'session.commentary.append',delegation_id=None,content=notice)
                if not future and pending and time.monotonic()-max(pending[0][2],last_input_at)>=1.2:
                    work_id,offset,_=pending.pop(0);text=fragments.take(offset)
                    if text:future=pool.submit(self.turn,identity,work_id,text)
                    else:send(socket,'session.commentary.append',delegation_id=work_id,content='Please ask the customer to repeat their last request; no complete transcript was received.')
                try: raw=socket.recv(timeout=0.3)
                except TimeoutError: continue
                event=json.loads(raw)
                if event.get('type')=='session.started' and not greeting_decided:
                    greeting_decided=True
                    if speech_started:
                        self.update(identity,greeting_status='skipped_conversation_started')
                    else:
                        greeting_id='greeting-'+str(uuid4())
                        send(socket,'session.instructions.append',event_id=greeting_id,delegation_id=None,
                             content=opening_instructions(locale))
                        greeting_sent_at=time.monotonic()
                        self.update(identity,greeting_status='sent')
                elif event.get('type')=='session.instructions.appended' and greeting_id and event.get('client_event_id')==greeting_id:
                    greeting_acked=True
                    self.update(identity,greeting_status='accepted')  # Acceptance is not proof of playback.
                elif event.get('type')=='session.input_transcript.delta':
                    speech_started=speech_started or bool(event.get('delta','').strip())
                    last_input_at=time.monotonic()
                    fragments.add(event)
                elif event.get('type')=='session.output_transcript.delta':
                    speech_started=speech_started or bool(event.get('delta','').strip())
                    if ending_at is not None:
                        last_output_at=time.monotonic(); closing_text=(closing_text+event.get('delta',''))[-400:]
                elif event.get('type')=='session.delegation.created':
                    item=event.get('delegation',{});did=item.get('id');offset=event.get('offset_ms')
                    if item.get('target')=='client' and isinstance(did,str) and 0<len(did)<=128 and isinstance(offset,(int,float)) and offset>=0 and did not in seen:
                        if len(seen)>=40:raise ValueError('voice_turn_limit')
                        seen.add(did);pending.append((did,offset,time.monotonic()))
                elif event.get('type')=='session.closed':
                    closed=True;final_usage=event.get('usage');break
                elif event.get('type')=='error':
                    if greeting_id and event.get('client_event_id')==greeting_id:
                        self.update(identity,greeting_status='failed')
                    raise RuntimeError('voice_provider_error')
        except Exception:
            reason='connection_lost'
        finally:
            ready.set()
            # Close media promptly, even while a read-only flow turn finishes.
            if not closed:
                try:
                    send(socket,'session.close')
                    until=time.monotonic()+3
                    while time.monotonic()<until:
                        event=json.loads(socket.recv(timeout=max(.1,until-time.monotonic())))
                        if event.get('type')=='session.closed':
                            closed=True;final_usage=event.get('usage');break
                except Exception:pass
            disconnect(socket);pool.shutdown(wait=False,cancel_futures=True)
            self.update(identity,'closed' if closed else 'failed',reason=reason if closed else 'close_unconfirmed',
                        remote_closed=closed,ended_at=int(time.time()),usage=final_usage if isinstance(final_usage,dict) else None)
            with self.sessions() as db:
                row=db.get(VoiceSession,identity)
                if row:audit(db,row,'voice_closed');db.commit()
            with self.lock:self.jobs.pop(identity,None)


def voice_router():
    router=APIRouter()

    @router.get('/api/voice/capabilities')
    def capabilities(user=Depends(customer_read),db=Depends(db_session)):
        rows=db.scalars(select(VoiceSession).where(VoiceSession.user_id==user.id,VoiceSession.status.in_((*ACTIVE,'failed')))).all()
        pending=next((r.id for r in rows if r.status in ACTIVE or (r.provider_id and not r.state.get('remote_closed'))),None)
        return {'enabled':enabled() and flow_enabled() and bool(api_key()),'maxSeconds':LIMIT_SECONDS,'voices':VOICES,'pendingSessionId':pending}

    @router.post('/api/voice/sessions')
    def start(body:StartVoice, request:Request,user=Depends(customer),auth=Depends(current_session),db=Depends(db_session)):
        if not enabled() or not flow_enabled() or not api_key():raise HTTPException(503,'voice_unavailable')
        if not body.sdp.startswith('v=0'):raise HTTPException(422,'validation')
        runtime=request.app.state.voice
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        if db.scalar(select(VoiceSession).where(VoiceSession.user_id==user.id,VoiceSession.request_key==body.requestKey)):
            # Never create a second billed session after an ambiguous response.
            raise HTTPException(409,'voice_start_exists')
        previous=db.scalars(select(VoiceSession).where(VoiceSession.user_id==user.id,VoiceSession.status.in_((*ACTIVE,'failed')))).all()
        if any(r.status in ACTIVE or (r.provider_id and not r.state.get('remote_closed')) for r in previous):raise HTTPException(409,'voice_active')
        with runtime.lock:
            if len(runtime.jobs)>=8:raise HTTPException(429,'rate_limited')
        if body.transactionId:transaction_evidence(db,user.id,body.transactionId)
        if body.requestId and not db.scalar(select(RequestCase).where(RequestCase.id==body.requestId,RequestCase.user_id==user.id)):raise HTTPException(404,'not_found')
        if body.conversationId:
            conv=db.scalar(select(Conversation).where(Conversation.id==body.conversationId,Conversation.user_id==user.id))
            if not conv:raise HTTPException(404,'not_found')
            require_open(db,conv)
            if body.transactionId and body.transactionId!=conv.transaction_id:raise HTTPException(409,'conversation_context_conflict')
            flow=db.get(ConversationFlow,conv.id)
            selected=flow.state.get('bank_binding',{}).get('request_id') if flow else None
            if body.requestId and selected!=body.requestId:raise HTTPException(409,'conversation_context_conflict')
        else:
            conv=Conversation(id=str(uuid4()),user_id=user.id,title=None,locale=body.locale,transaction_id=body.transactionId)
            db.add(conv);db.flush()
        stamp=int(time.time())
        row=VoiceSession(id=str(uuid4()),user_id=user.id,conversation_id=conv.id,auth_hash=auth[0].token_hash,
            request_key=body.requestKey,status='connecting',locale=body.locale,created_at=stamp,expires_at=stamp+LIMIT_SECONDS,
            heartbeat_at=stamp,state={'request_id':body.requestId,'revision':0,'delegations':{}})
        db.add(row);audit(db,row,'voice_started');db.commit()
        socket=None
        try:
            provider_id,answer=runtime.provider.create(body.sdp,body.locale,body.voice)
            row.provider_id=provider_id;db.commit()
            socket=runtime.provider.attach(provider_id)
            # Creation may outlive logout or the browser's connection lease.
            if not runtime.live(row.id):raise RuntimeError('voice_session_ended')
            runtime.start(row.id,socket)
            return {**view(row),'sdp':answer,'status':'active'}
        except Exception:
            if socket:
                try:send(socket,'session.close')
                except Exception:pass
                finally:disconnect(socket)
            row.status='failed';row.state={**row.state,'reason':'connection_lost'};db.commit()
            if row.provider_id:runtime.recover_one(row.id)
            raise HTTPException(503,'voice_connection') from None

    def owned(identity,user,db):
        row=db.scalar(select(VoiceSession).where(VoiceSession.id==identity,VoiceSession.user_id==user.id))
        if not row:raise HTTPException(404,'not_found')
        return row

    @router.post('/api/voice/sessions/{identity}/heartbeat')
    def heartbeat(identity:str,user=Depends(customer),auth=Depends(current_session),db=Depends(db_session)):
        row=owned(identity,user,db)
        if row.auth_hash!=auth[0].token_hash:raise HTTPException(409,'voice_session_ended')
        row.heartbeat_at=int(time.time());db.commit()
        return view(row)

    @router.post('/api/voice/sessions/{identity}/close')
    def close(identity:str,request:Request,user=Depends(customer),db=Depends(db_session)):
        row=owned(identity,user,db);runtime=request.app.state.voice
        with runtime.lock: running=row.id in runtime.jobs
        if running:
            runtime.close(row.id)
            with runtime.lock:job=runtime.jobs.get(row.id)
            if job:job[1].join(timeout=4)
        elif enabled() and row.provider_id and not row.state.get('remote_closed'):runtime.recover_one(row.id)
        db.expire_all();row=db.get(VoiceSession,identity)
        return view(row)

    return router
