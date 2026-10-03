"""Santiago's document contracts adapted to the persistent authenticated chat."""
import hashlib
import json
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from pydantic import Field, model_validator
from sqlalchemy import select, func
from .models import User, Product, Transaction, RequestCase, Conversation, ConversationFlow, Message, ChatDocument, AuditEvent, now, iso_utc
from .schemas import StrictModel, Locale
from .security import customer, customer_read, db_session
from .document_renderer import generar_pdf

DOCUMENT_INTENTS = {'documents','account-balance','account-activity','my-cards','request-status'}
MAX_ROWS = 250
TITLES = {
    'statement': ('Estado de cuenta informativo','Informational account statement','Extrato informativo'),
    'products_summary': ('Resumen de productos','Product summary','Resumo de produtos'),
    'requests_summary': ('Seguimiento de solicitudes','Request tracking','Acompanhamento de solicitações'),
}


class DocumentInput(StrictModel):
    kind: Literal['statement','products_summary','requests_summary']
    scope: Literal['all','selected']
    productId: str | None = Field(default=None, min_length=1, max_length=64)
    requestId: str | None = Field(default=None, min_length=1, max_length=64)
    startDate: str | None = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    endDate: str | None = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    allHistory: bool = False
    locale: Locale
    requestKey: str = Field(min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')

    @model_validator(mode='after')
    def selection(self):
        if self.scope == 'all' and (self.productId or self.requestId): raise ValueError('Unexpected selected reference')
        if self.scope == 'selected' and not (self.requestId if self.kind == 'requests_summary' else self.productId): raise ValueError('Select a reference')
        if self.kind == 'requests_summary' and self.productId or self.kind != 'requests_summary' and self.requestId: raise ValueError('Wrong reference kind')
        if self.kind != 'statement' and (self.startDate or self.endDate or self.allHistory): raise ValueError('Unexpected period')
        if self.kind == 'statement':
            if self.allHistory:
                if self.startDate or self.endDate: raise ValueError('Choose one period')
            else:
                start, end = date.fromisoformat(self.startDate or ''), date.fromisoformat(self.endDate or '')
                if start > end or (end-start).days > 366: raise ValueError('Select up to one year')
        return self


def document_view(doc):
    return {'id':doc.id,'filename':doc.filename,'kind':doc.kind,'locale':doc.locale,
            'title':TITLES[doc.kind][('es','en','pt').index(doc.locale)],'createdAt':iso_utc(doc.created_at),
            'conversationId':doc.conversation_id,'details':doc.details}


def can_document(row):
    ctx = row.state['context'] if row else {}
    return ctx.get('triage',{}).get('family') == 'query' and ctx.get('jev',{}).get('status') == 'ok' and ctx.get('intent') in DOCUMENT_INTENTS


def document_packet(db, owner, body):
    """Allowlisted fields and owner joins only. No SQL, HTML or bank data from a model."""
    def bounded(query):
        rows = db.scalars(query.limit(MAX_ROWS+1)).all()
        if len(rows) > MAX_ROWS: raise HTTPException(422, 'document_too_many_rows')
        return rows
    facts=[]; fields={}; stamp=now().isoformat()
    def add(table,row,values): facts.append({'source_ref':table+':'+row.id,'values':{'id':row.id,**values}})
    def money(minor,currency): return None if minor is None else f'{currency} {Decimal(minor)/100:,.2f}'
    def iso(value): return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if body.kind != 'requests_summary':
        q=select(Product).where(Product.user_id==owner).order_by(Product.id)
        if body.productId:q=q.where(Product.id==body.productId)
        rows=bounded(q)
        if body.productId and not rows:raise HTTPException(404,'not_found')
        for r in rows:add('products',r,{'type':r.type,'last4':r.last4,'balance_display':money(r.balance_minor,r.currency)})
    if body.kind == 'statement':
        q=select(Transaction).join(Product,(Product.id==Transaction.product_id)&(Product.user_id==Transaction.user_id)).where(Transaction.user_id==owner,Product.user_id==owner).order_by(Transaction.occurred_at.desc(),Transaction.id.desc())
        if body.productId:q=q.where(Transaction.product_id==body.productId)
        fields={'all_history':body.allHistory}
        if not body.allHistory:
            zone=ZoneInfo('America/Mexico_City')
            start=datetime.combine(date.fromisoformat(body.startDate),time.min,zone).astimezone(timezone.utc)
            end=datetime.combine(date.fromisoformat(body.endDate)+timedelta(days=1),time.min,zone).astimezone(timezone.utc)
            q=q.where(Transaction.occurred_at>=start,Transaction.occurred_at<end)
            fields.update(start=start.isoformat(),end=end.isoformat())
        for r in bounded(q):add('transactions',r,{'product_id':r.product_id,'occurred_at':iso(r.occurred_at),'merchant':r.merchant,'amount_display':money(r.amount_minor,r.currency),'status':r.status})
    if body.kind == 'requests_summary':
        q=select(RequestCase).where(RequestCase.user_id==owner).order_by(RequestCase.created_at.desc(),RequestCase.id)
        if body.requestId:q=q.where(RequestCase.id==body.requestId)
        rows=bounded(q)
        if body.requestId and not rows:raise HTTPException(404,'not_found')
        for r in rows:add('requests',r,{'service':r.service,'status':r.status,'created_at':iso(r.created_at),'updated_at':iso(r.updated_at)})
    return {'type':body.kind,'fields':fields,'generated_at':stamp,'facts':facts}


def document_router(message_view):
    router=APIRouter()

    @router.post('/api/conversations/{conversation_id}/documents')
    def create(conversation_id:str, body:DocumentInput, user=Depends(customer), db=Depends(db_session)):
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        conv=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.user_id==user.id).with_for_update())
        if not conv:raise HTTPException(404,'not_found')
        fingerprint=hashlib.sha256(json.dumps({'conversation':conv.id,**body.model_dump(exclude={'requestKey'})},sort_keys=True).encode()).hexdigest()
        previous=db.scalar(select(ChatDocument).where(ChatDocument.user_id==user.id,ChatDocument.request_key==body.requestKey))
        if previous:
            if previous.fingerprint!=fingerprint:raise HTTPException(409,'conflict')
            return {'document':document_view(previous),'message':message_view(db.get(Message,previous.message_id))}
        if not can_document(db.get(ConversationFlow,conv.id)):raise HTTPException(409,'document_query_required')
        if db.scalar(select(func.count()).select_from(ChatDocument).where(ChatDocument.conversation_id==conv.id))>=20:raise HTTPException(409,'document_limit')
        packet=document_packet(db,user.id,body)
        content=generar_pdf(packet,customer_name=user.name,language=body.locale)
        if len(content)>2_000_000:raise HTTPException(422,'document_too_many_rows')
        title=TITLES[body.kind][('es','en','pt').index(body.locale)]
        reply=('Tu documento está listo. Puedes descargarlo aquí o desde Documentos solicitados en Mis solicitudes.',
               'Your document is ready. Download it here or from Requested documents in My requests.',
               'Seu documento está pronto. Baixe aqui ou em Documentos solicitados em Minhas solicitações.')[('es','en','pt').index(body.locale)]
        message=Message(id=str(uuid4()),user_id=user.id,conversation_id=conv.id,role='assistant',content=title+'\n'+reply,locale=body.locale)
        db.add(message);db.flush()
        ident=str(uuid4());doc=ChatDocument(id=ident,user_id=user.id,conversation_id=conv.id,message_id=message.id,
            kind=body.kind,locale=body.locale,filename=f'nexqori-{body.kind}-{ident[:8]}.pdf',request_key=body.requestKey,
            fingerprint=fingerprint,content=content,details={
                'scope':body.scope,'accountLast4':db.get(Product,body.productId).last4 if body.productId else None,
                'requestId':body.requestId,'startDate':body.startDate,'endDate':body.endDate,'allHistory':body.allHistory,
                'recordCount':len(packet['facts'])})
        db.add(doc);message.document=doc;conv.updated_at=now()
        db.add(AuditEvent(id=str(uuid4()),user_id=user.id,actor_id=user.id,conversation_id=conv.id,action='document_generated'))
        db.flush();result={'document':document_view(doc),'message':message_view(message)};db.commit();return result

    @router.get('/api/documents')
    def listing(offset:int=Query(default=0,ge=0),selected:str|None=Query(default=None,max_length=64),user=Depends(customer_read),db=Depends(db_session)):
        rows=db.scalars(select(ChatDocument).where(ChatDocument.user_id==user.id).order_by(ChatDocument.created_at.desc(),ChatDocument.id.desc()).offset(offset).limit(21)).all()
        # A deep link stays useful after the document moves to a later page.
        chosen=db.scalar(select(ChatDocument).where(ChatDocument.user_id==user.id,ChatDocument.id==selected)) if selected else None
        return {'documents':[document_view(d) for d in rows[:20]],'nextOffset':offset+20 if len(rows)>20 else None,
                'selected':document_view(chosen) if chosen else None}

    @router.get('/api/documents/{document_id}')
    def download(document_id:str,user=Depends(customer_read),db=Depends(db_session)):
        doc=db.scalar(select(ChatDocument).where(ChatDocument.id==document_id,ChatDocument.user_id==user.id))
        if not doc:raise HTTPException(404,'not_found')
        db.add(AuditEvent(id=str(uuid4()),user_id=user.id,actor_id=user.id,conversation_id=doc.conversation_id,action='document_downloaded'))
        content,filename=doc.content,doc.filename;db.commit()
        return Response(content,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    return router
