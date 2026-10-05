"""Read-only bridge to the local bank. Identity always comes from its session.

Only fixed endpoints and the bank's read-tool allowlist are reachable. Credentials
are transient, never stored in checkpoints or included in model inputs.
"""
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.agent_routing import TOOLS, tools_for

BANK_URL='http://127.0.0.1:5180'
BANK_ORIGIN='http://localhost:5180'
COOKIE='nexqori_session'
http_client=httpx.Client


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    transaction_id: str | None=Field(default=None,min_length=1,max_length=64)
    request_id: str | None=Field(default=None,min_length=1,max_length=64)


class BankReader:
    def __init__(self, token):
        if not token or len(token)!=64: raise HTTPException(401,'bank_session_required')
        self._token=token
        self._csrf=None
        session=self._request('GET','/api/session')
        user=session.get('user',{})
        if user.get('role')!='customer': raise HTTPException(403,'bank_customer_required')
        self.user={key:user[key] for key in ('id','name','role')}
        self._csrf=session['csrfToken']

    def _request(self, method, path, body=None):
        # Paths are hard-coded by this module; neither models nor browser input
        # can choose an endpoint, origin, role, owner, SQL or financial command.
        headers={'Origin':BANK_ORIGIN}
        if self._csrf: headers['X-CSRF-Token']=self._csrf
        try:
            with http_client(timeout=httpx.Timeout(8,connect=2),follow_redirects=False,trust_env=False,cookies={COOKIE:self._token}) as client:
                response=client.request(method,BANK_URL+path,headers=headers,json=body)
            if response.status_code==401: raise HTTPException(401,'bank_session_required')
            if response.status_code==403: raise HTTPException(403,'bank_read_forbidden')
            if response.status_code==404: raise HTTPException(404,'bank_reference_unavailable')
            if response.status_code!=200: raise HTTPException(503,'bank_unavailable')
            return response.json()
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,'bank_unavailable') from None

    def read(self, intent, tool, language='es', reference=None):
        if tool not in tools_for(intent) or TOOLS[tool]['kind']!='read':
            raise HTTPException(403,'bank_read_forbidden')
        body={'intent':intent,'tool':tool,'locale':language}
        if reference: body['referenceId']=reference
        value=self._request('POST','/api/assistant/tools/read',body)
        return {**value,'observed_at':datetime.now(timezone.utc).isoformat()}

    def transactions(self, language='es'):
        value=self.read('account-activity','read-transactions',language)
        return {'user':self.user,**value['data'],'auditEventId':value['auditEventId']}

    def collect(self, intent, binding, language, fields):
        if binding['owner_id']!=self.user['id']: raise HTTPException(404,'bank_reference_unavailable')
        planned=[tool for tool in tools_for(intent) if TOOLS[tool]['kind']=='read']
        planned.sort(key=lambda tool:0 if tool=='read-transaction-evidence' else 1 if tool=='read-request-status' else 2)
        reads=[];missing=[];transaction=None;linked_request=None;failure=None
        for tool in planned:
            reference=None
            if tool=='read-transaction-evidence':
                reference=binding.get('transaction_id')
                if not reference:
                    if intent in ('unrecognized-charge','incorrect-charge','payment-status'): missing.append('transaction_id')
                    continue
            elif tool=='read-request-status':
                reference=binding.get('request_id') or linked_request
                if not reference:
                    if intent=='request-status': missing.append('request_id')
                    continue
                if binding.get('request_id') and transaction and binding['request_id']!=linked_request:
                    failure='bank_reference_conflict';break
            try: result=self.read(intent,tool,language,reference)
            except HTTPException as error:
                failure=error.detail;break
            reads.append(result)
            if tool=='read-transaction-evidence':
                transaction=result
                linked_request=(result['data'].get('request') or {}).get('id')
        facts=[]
        if transaction:
            tx=transaction['data']['transaction']
            values={'movement':tx['merchant']+' · '+tx['id'],'date':tx['date'],
                    'amount':str(Decimal(tx['amountMinor'])/100)+' '+tx['currency'],'status':tx['status']}
            # Applicable recorded conditions establish the difference without
            # asking the customer to repeat data already held by the bank.
            # This is not proof that extras were unauthorized or permission to refund.
            agreement=(transaction['data'].get('historyComparison') or {}).get('serviceAgreement') or {}
            if intent=='incorrect-charge' and agreement.get('status') in ('above-base','within-base'):
                label=('base del plan registrada','recorded plan base','base do plano registrada')[('es','en','pt').index(language)]
                values['difference']=f"{Decimal(agreement['differenceMinor'])/100} {tx['currency']} ({label})"
            facts=[{'field':field,'value':value,'status':'verified','source':'nexqori_records','reference_id':tx['id'],
                    'audit_event_id':transaction['auditEventId'],'observed_at':transaction['observed_at']}
                   for field,value in values.items() if field in fields]
        for row in reads:
            if row['tool']=='read-request-status' and 'reference' in fields:
                facts.append({'field':'reference','value':row['data']['request']['id'],'status':'verified','source':'nexqori_records',
                              'reference_id':row['data']['request']['id'],'audit_event_id':row['auditEventId'],'observed_at':row['observed_at']})
        return {'status':'unavailable' if failure else 'needs_reference' if missing else 'read','error':failure,'source':'authenticated_bank','reads':reads,
                'verified_facts':facts,'missing_references':missing,'external_processor_logs':False,
                'application_error_logs':False,'executed_operations':[]}


def authenticate(request: Request, owner_id=None):
    reader=BankReader(request.cookies.get(COOKIE))
    if owner_id and reader.user['id']!=owner_id: raise HTTPException(404,'bank_reference_unavailable')
    return reader


def for_execution(request, state):
    binding=state.get('bank_binding')
    return authenticate(request,binding['owner_id']) if binding else None
