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
from .models import VoiceSession, Session, Conversation, ConversationFlow, User, RequestCase, AuditEvent
from .security import customer, customer_read, current_session, db_session
from .schemas import StrictModel, Locale
from .transaction_context import transaction_evidence
from .workflow_chat import FlowMessage, run_chat_turn, enabled as flow_enabled
from .voice_provider import LiveProvider, VOICES, enabled, api_key, send

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


def safe_spoken_result(reply, locale):
    """Allowlisted descriptions, never interpolate bank values or model text."""
    flow = reply.get('flow') or {}
    # Known field names select fixed questions. Never relay model-generated
    # questions or bank-enriched reply text to the external speech model.
    questions={
        'difference':('¿Qué importe esperabas pagar?', 'What amount did you expect to pay?', 'Qual valor você esperava pagar?'),
        'date':('¿En qué fecha ocurrió?', 'On what date did it happen?', 'Em que data aconteceu?'),
        'transaction_id':('Termina la llamada y elige en pantalla el movimiento que quieres revisar.', 'End the call and select the transaction you want to review on screen.', 'Encerre a chamada e selecione na tela a movimentação que deseja revisar.'),
        'request_id':('Termina la llamada y elige en Detalles el caso que quieres consultar.', 'End the call and choose the case you want to check in Details.', 'Encerre a chamada e escolha em Detalhes o caso que deseja consultar.')}
    missing=flow.get('missing_fields') or []
    if missing and missing[0] in questions:return questions[missing[0]][('es','en','pt').index(locale)]
    key = 'review' if flow.get('canRegister') else 'question' if flow.get('missing_fields') else 'screen'
    messages = {
        'review':('El caso está listo. Termina la llamada para revisar el resumen en pantalla y decidir si quieres registrarlo.',
            'The case is ready. End the call to review the summary on screen and decide whether to register it.',
            'O caso está pronto. Encerre a chamada para revisar o resumo na tela e decidir se deseja registrá-lo.'),
        'question':('Necesito un dato más. La pregunta está en el chat; puedes responderla por voz.',
            'I need one more detail. The question is in the chat; you can answer by voice.',
            'Preciso de mais uma informação. A pergunta está no chat; você pode responder por voz.'),
        'screen':('La respuesta está en tu chat. Revisa los detalles en pantalla y dime cómo seguimos.',
            'The answer is in your chat. Review the details on screen and tell me how to continue.',
            'A resposta está no chat. Confira os detalhes na tela e me diga como continuar.')}
    return messages[key][('es','en','pt').index(locale)]


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
        chosen = sorted((f for f in self.fragments if f['event_id'] not in self.used and f['end_ms']<=offset),
                        key=lambda f:(f['start_ms'],f['end_ms']))
        text = ''.join(f['delta'] for f in chosen).strip()
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
            reply=run_chat_turn(FlowMessage(message=text,locale=row.locale,conversationId=conv.id,
                transactionId=conv.transaction_id,requestId=selected_request,requestKey=key),
                user,db,self.conversation_view,self.message_view)
            # The shared service committed the turn. Its key prevents duplicate
            # messages even if a crash occurs before this receipt is committed.
            db.expire_all(); row=db.scalar(select(VoiceSession).where(VoiceSession.id==identity).with_for_update())
            receipts=dict(row.state.get('delegations',{}))
            if delegation_id not in receipts:
                receipts[delegation_id]=key
                row.state={**row.state,'reply':reply,'revision':row.state.get('revision',0)+1,'delegations':receipts}
                audit(db,row,'voice_turn');db.commit()
            return safe_spoken_result(reply,row.locale)

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
        try:
            self.update(identity,'active');ready.set()
            while not stop.is_set() and self.live(identity):
                if future and future.done():
                    result=future.result();send(socket,'session.commentary.append',delegation_id=work_id,content=result)
                    future=None
                if not future and pending and time.monotonic()-pending[0][2]>=0.6:
                    work_id,offset,_=pending.pop(0);text=fragments.take(offset)
                    if text:future=pool.submit(self.turn,identity,work_id,text)
                    else:send(socket,'session.commentary.append',delegation_id=work_id,content='Please ask the customer to repeat their last request; no complete transcript was received.')
                try: raw=socket.recv(timeout=0.3)
                except TimeoutError: continue
                event=json.loads(raw)
                if event.get('type')=='session.input_transcript.delta': fragments.add(event)
                elif event.get('type')=='session.delegation.created':
                    item=event.get('delegation',{});did=item.get('id');offset=event.get('offset_ms')
                    if item.get('target')=='client' and isinstance(did,str) and 0<len(did)<=128 and isinstance(offset,(int,float)) and offset>=0 and did not in seen:
                        if len(seen)>=40:raise ValueError('voice_turn_limit')
                        seen.add(did);pending.append((did,offset,time.monotonic()))
                elif event.get('type')=='session.closed':
                    closed=True;final_usage=event.get('usage');break
                elif event.get('type')=='error':raise RuntimeError('voice_provider_error')
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
