from __future__ import annotations

import json
import threading
import asyncio
import queue
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, APIRouter, HTTPException, Request, Query
from uuid import UUID
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .benchmark import run_benchmark
from .data import ROOT, corpus, digest, taxonomy
from .decision import INSTRUCTIONS, proposed_action, request_preview
from .decision import LABELS
from .storage import read_conversations, save_conversation
from . import storage
from .providers import classify, provider_status
from .dialogue import respond, overrides, save_instructions, contract_for, problem_intents
from backend.agent_routing import route_plan
from . import flow_engine
from . import workflow_editor as editor
from . import app_diagnostics
from . import workflow_execution as execution
from . import bank_context as bank
from .bank_context import Selection as BankSelection

app = FastAPI(title="Nexqori · Intent Lab", docs_url="/lab-api/docs", redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
lock = threading.Lock()
provider_lock = threading.Lock()
latest = None
editor_router = APIRouter(prefix="/lab-api/editor")


@app.middleware("http")
async def local_only(request: Request, call_next):
    if request.method in ("POST", "PUT"):
        if request.headers.get("origin") not in (None, "http://localhost:5190", "http://127.0.0.1:5190", "http://localhost:5191", "http://127.0.0.1:5191"):
            return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
        # Provider inputs are saved only in private local run records.
        editor_path=request.url.path.removeprefix('/api')
        limit = 96000 if editor_path.startswith('/lab-api/editor/') and not request.url.path.endswith(('/run','/run-stream','/advance','/replay')) else 24000
        if len(await request.body()) > limit:
            return JSONResponse({"error": "input_too_long"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class Preview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["es", "en", "pt"] = "es"
    messages: list[Message] = Field(min_length=1, max_length=10)
    instructions: str = Field(default=INSTRUCTIONS, min_length=1, max_length=4000)


class Conversation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    language: Literal["es", "en", "pt"]
    messages: list[Message] = Field(min_length=1, max_length=10)
    expected: str | None = None
    instructions: str = Field(default=INSTRUCTIONS, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def valid(self):
        if not self.title.strip() or any(not m.content.strip() for m in self.messages):
            raise ValueError("Empty title or message")
        if self.messages[-1].role != "user":
            raise ValueError("Conversation must end with customer input")
        if self.expected is not None and self.expected not in LABELS:
            raise ValueError("Unknown expected intent")
        return self

class Dialogue(Preview):
    context: str = Field(default="", max_length=2000)
    thread_id: UUID | None = None

    @model_validator(mode="after")
    def ends_with_user(self):
        if self.messages[-1].role!="user" or any(not m.content.strip() for m in self.messages): raise ValueError("Customer input required")
        return self

class WorkflowInstructions(BaseModel):
    model_config=ConfigDict(extra="forbid")
    language: Literal["es","en","pt"]
    instructions: str=Field(max_length=2000)

class EditorSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    graph: editor.Graph
    revision: int | None=Field(default=None,ge=1)

class EditorRun(Dialogue):
    bank: BankSelection | None=None
    revision: int=Field(ge=1)
    incident_id: UUID | None=None
    mode: Literal['step','full']='full'

class EditorAdvance(BaseModel):
    bank: BankSelection | None=None
    model_config=ConfigDict(extra='forbid')
    version: int=Field(ge=0)
    node_id: str=Field(min_length=1,max_length=50)
    mode: Literal['step','full']='step'
    reply: str | None=Field(default=None,min_length=1,max_length=2000)

class EditorReplay(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int=Field(ge=0)
    node_id: str=Field(min_length=1,max_length=50)

@editor_router.get('/template')
def editor_template(kind: Literal['banking','app']='banking'):
    return {'graph':editor.template(kind),'fields':list(flow_engine.QUESTIONS),'taxonomy':taxonomy()}

@editor_router.post('/master-workflow')
def editor_master():
    with lock:
        try:return editor.master_workflow()
        except RuntimeError:raise HTTPException(409,'workflow_limit') from None

@editor_router.post('/app-check')
def editor_app_check():
    with lock: return app_diagnostics.reproduce()

@editor_router.get('/notifications')
def editor_notifications():
    return {'notifications':list(reversed(app_diagnostics.notifications()))[:30]}

@editor_router.get('/workflows')
def editor_list():
    return {'workflows':editor.list_workflows()}

@editor_router.post('/validate')
def editor_validate(body: EditorSave):
    return editor.validate_graph(body.graph.model_dump()) | {'graph':body.graph.model_dump()}

@editor_router.post('/workflows',status_code=201)
def editor_create(body: EditorSave):
    with lock:
        try: return editor.save_workflow(body.graph.model_dump())
        except RuntimeError: raise HTTPException(409,'workflow_limit') from None

@editor_router.get('/workflows/{workflow_id}')
def editor_read(workflow_id: UUID):
    try: return editor.read_workflow(workflow_id)
    except FileNotFoundError: raise HTTPException(404,'not_found') from None

@editor_router.put('/workflows/{workflow_id}')
def editor_save(workflow_id: UUID,body: EditorSave):
    with lock:
        try: return editor.save_workflow(body.graph.model_dump(),workflow_id,body.revision)
        except FileNotFoundError: raise HTTPException(404,'not_found') from None
        except RuntimeError: raise HTTPException(409,'revision_conflict') from None

@editor_router.post('/workflows/{workflow_id}/run')
def editor_run(workflow_id: UUID,body: EditorRun,request: Request):
    if body.context: raise HTTPException(422,'configure_context_in_node')
    try: record=editor.read_workflow(workflow_id)
    except FileNotFoundError: raise HTTPException(404,'not_found') from None
    if record['revision']!=body.revision: raise HTTPException(409,'revision_conflict')
    if not editor.validate_graph(record['graph'])['valid']: raise HTTPException(422,'invalid_graph')
    reader=bank.authenticate(request) if body.bank is not None else None
    binding={'owner_id':reader.user['id'],**body.bank.model_dump()} if reader else None
    if not provider_lock.acquire(blocking=False): raise HTTPException(409,'classification_running')
    try:
        state=execution.create(record,[m.model_dump() for m in body.messages],body.language,str(body.thread_id) if body.thread_id else None,str(body.incident_id) if body.incident_id else None,binding)
        return execution.advance(state,body.mode,bank_reader=reader)
    finally: provider_lock.release()

@editor_router.post('/workflows/{workflow_id}/run-stream')
def editor_run_stream(workflow_id: UUID,body: EditorRun,request: Request):
    if body.context: raise HTTPException(422,'configure_context_in_node')
    try: record=editor.read_workflow(workflow_id)
    except FileNotFoundError: raise HTTPException(404,'not_found') from None
    if record['revision']!=body.revision: raise HTTPException(409,'revision_conflict')
    if not editor.validate_graph(record['graph'])['valid']: raise HTTPException(422,'invalid_graph')
    reader=bank.authenticate(request) if body.bank is not None else None
    binding={'owner_id':reader.user['id'],**body.bank.model_dump()} if reader else None
    if not provider_lock.acquire(blocking=False): raise HTTPException(409,'classification_running')
    try:state=execution.create(record,[m.model_dump() for m in body.messages],body.language,
                str(body.thread_id) if body.thread_id else None,str(body.incident_id) if body.incident_id else None,binding)
    except Exception:
        provider_lock.release()
        raise
    return execution_stream(state,body.mode,bank_reader=reader)

@editor_router.get('/executions/{execution_id}')
def editor_execution(execution_id: UUID,request: Request):
    try:
        state=execution.read(execution_id)
        bank.for_execution(request,state)
        return execution.view(state)
    except FileNotFoundError:raise HTTPException(404,'not_found') from None

@editor_router.post('/executions/{execution_id}/replay')
def editor_replay(execution_id: UUID,body: EditorReplay,request: Request):
    if not provider_lock.acquire(blocking=False):raise HTTPException(409,'classification_running')
    try:
        parent=execution.read(execution_id)
        reader=bank.for_execution(request,parent)
        state,reused=execution.replay(parent,body.version,body.node_id)
    except (FileNotFoundError,RuntimeError,ValueError) as error:
        provider_lock.release()
        if isinstance(error,FileNotFoundError):raise HTTPException(404,'not_found') from None
        raise HTTPException(409 if isinstance(error,RuntimeError) else 422,str(error)) from None
    except Exception:
        provider_lock.release()
        raise
    if reused:
        provider_lock.release()
        return JSONResponse({'detail':'replay_exists','execution_id':state['id']},status_code=409)
    return execution_stream(state,'step',bank_reader=reader)

@editor_router.post('/executions/{execution_id}/advance')
def editor_advance(execution_id: UUID,body: EditorAdvance,request: Request):
    if not provider_lock.acquire(blocking=False):raise HTTPException(409,'classification_running')
    try:
        state=execution.read(execution_id)
        reader=bank.for_execution(request,state)
        selection=body.bank.model_dump() if body.bank is not None else None
        execution.preflight(state,body.version,body.node_id,body.reply,selection)
    except (FileNotFoundError,RuntimeError,ValueError) as error:
        provider_lock.release()
        if isinstance(error,FileNotFoundError):raise HTTPException(404,'not_found') from None
        raise HTTPException(409 if isinstance(error,RuntimeError) else 422,str(error)) from None
    except Exception:
        provider_lock.release()
        raise
    return execution_stream(state,body.mode,body.reply,reader,selection)

def execution_stream(state,mode,reply=None,bank_reader=None,bank_selection=None):
    events=queue.Queue()
    events.put({'event':'execution_created','result':execution.view(state)})
    def execute():
        try:
            result=execution.advance(state,mode,reply,events.put,bank_reader,bank_selection)
            phase=result['execution']['phase']
            events.put({'event':'complete' if phase=='completed' else phase,'result':result})
        except Exception:
            events.put({'event':'error','code':'execution_failed'})
        finally:
            provider_lock.release()
            events.put(None)
    # A disconnected browser cannot trigger a second execution. The bounded run finishes,
    # persists its trace and releases the lock even if its progress is no longer viewed.
    threading.Thread(target=execute,daemon=True).start()
    async def stream():
        while True:
            try: event=await asyncio.to_thread(events.get,True,1)
            except queue.Empty:
                yield json.dumps({'event':'heartbeat'})+'\n'
                continue
            if event is None: break
            yield json.dumps(event,ensure_ascii=False)+'\n'
    return StreamingResponse(stream(),media_type='application/x-ndjson',headers={'X-Accel-Buffering':'no'})

@editor_router.get('/bank/session')
def editor_bank_session(request: Request):
    return {'user':bank.authenticate(request).user}

@editor_router.post('/bank/records')
def editor_bank_records(request: Request,language: Literal['es','en','pt']='es'):
    return bank.authenticate(request).transactions(language)

@editor_router.get('/cases')
def editor_cases(language: Literal['es','en','pt']='es'):
    evidence=json.loads((ROOT/'evidence.json').read_text(encoding='utf-8'))
    examples={}
    for row in corpus():
        if row['language']==language and row['slice']=='standard': examples.setdefault(row['expected'],row['text'])
    examples['request-status']={'es':'Quiero saber cómo va mi solicitud con folio NQ-123456.','en':'I want to check my request with reference NQ-123456.','pt':'Quero consultar minha solicitação com protocolo NQ-123456.'}[language]
    rows=flow_engine.flow_map(language)['definitions']
    for row in rows:
        row['evidence']=next((p for p in evidence['problems'] if p['intent']==row['intent']),None)
        row['example']=examples[row['intent']]
        row['example_source']='authored_category_example'
    return {'cases':rows}

@editor_router.get('/case-template/{intent}')
def editor_case_template(intent: str):
    if intent not in LABELS: raise HTTPException(404,'not_found')
    return editor.template()

class FlowEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Literal['es', 'en', 'pt']
    revision: int = Field(ge=0)
    questions: dict[str, str]
    instructions: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def bounded_questions(self):
        if len(self.questions) > 6 or any(not text.strip() or len(text) > 300 for text in self.questions.values()):
            raise ValueError('invalid_questions')
        return self

@app.get('/lab-api/flow-map')
def get_flow_map(language: Literal['es', 'en', 'pt']='es'):
    return flow_engine.flow_map(language)

@app.get('/lab-api/flow-history')
def flow_history(language: Literal['es', 'en', 'pt']='es'):
    rows=[]
    paths=sorted((storage.DATA_DIR/'runs').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    for path in paths:
        try:
            record=json.loads(path.read_text(encoding='utf-8'))
            result=record['result']
            if record.get('kind')!='flow' or result.get('language')!=language: continue
            rows.append({key:result[key] for key in ('id','created_at','state','thread_id')} | {'title':(result.get('definition') or {}).get('title','')})
            if len(rows)==30: break
        except (ValueError,KeyError): continue
    return {'runs':rows}

@app.put('/lab-api/flow-map/{intent}')
def update_flow_map(intent: str, body: FlowEdit):
    with lock:
        try:
            return flow_engine.save_definition(intent, body.language, body.revision, body.questions, body.instructions)
        except ValueError:
            raise HTTPException(422, 'invalid_fields') from None
        except RuntimeError:
            raise HTTPException(409, 'revision_conflict') from None

@app.post('/lab-api/flow-run')
def run_flow(body: Dialogue):
    if body.context: raise HTTPException(422, 'use_customer_messages_for_context')
    if not provider_lock.acquire(blocking=False): raise HTTPException(409, 'classification_running')
    try:
        return flow_engine.evaluate([m.model_dump() for m in body.messages], body.language, body.instructions,
                                    str(body.thread_id) if body.thread_id else None)
    finally:
        provider_lock.release()

@app.get('/lab-api/workflows')
def workflows(language: Literal['es','en','pt']='es'):
    return {'contracts':[contract_for(intent,language) for intent in sorted(problem_intents())]}

@app.put('/lab-api/workflows/{intent}')
def set_instructions(intent: str, body: WorkflowInstructions):
    if intent not in problem_intents(): raise HTTPException(404,'not_found')
    with lock:
        save_instructions(intent,body.language,body.instructions)
    return contract_for(intent,body.language)

@app.post('/lab-api/dialogue')
def dialogue(body: Dialogue):
    if not provider_lock.acquire(blocking=False): raise HTTPException(409,'classification_running')
    try:
        return respond([m.model_dump() for m in body.messages],body.language,body.instructions,body.context,str(body.thread_id) if body.thread_id else None)
    finally:
        provider_lock.release()

@app.get('/lab-api/runs')
def run_history(offset: int=Query(0,ge=0,le=100000)):
    paths=sorted((storage.DATA_DIR/'runs').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    rows=[]
    for path in paths[offset:offset+30]:
        try:
            record=json.loads(path.read_text(encoding='utf-8'));result=record['result']
            if result.get('bank_context'): continue
            rows.append({k:result.get(k) for k in ('id','created_at','thread_id')}|{'kind':record.get('kind','classification'),'actor':record.get('actor','local_operator'),'intent':result.get('jev',{}).get('intent'),'jev_status':result.get('jev',{}).get('status'),'llm_status':result.get('llm',{}).get('status')})
        except (ValueError,KeyError): continue
    return {'runs':rows,'nextOffset':offset+30 if len(paths)>offset+30 else None}

@app.get('/lab-api/runs/{run_id}')
@app.get('/api/lab-api/runs/{run_id}')
def run_detail(run_id: UUID,request: Request):
    path=storage.DATA_DIR/'runs'/f'{run_id}.json'
    if not path.exists(): raise HTTPException(404,'not_found')
    record=json.loads(path.read_text(encoding='utf-8'))
    binding=record.get('result',{}).get('bank_context')
    if binding: bank.authenticate(request,binding['owner_id'])
    return record


@app.get("/lab-api/conversations")
def conversations():
    return read_conversations()


@app.post("/lab-api/conversations", status_code=201)
def create_conversation(body: Conversation):
    try:
        return save_conversation(body.model_dump())
    except ValueError:
        raise HTTPException(409, detail="conversation_limit") from None


@app.put("/lab-api/conversations/{conversation_id}")
def update_conversation(conversation_id: str, body: Conversation):
    try:
        return save_conversation(body.model_dump(), conversation_id)
    except KeyError:
        raise HTTPException(404, detail="conversation_not_found") from None


@app.get("/lab-api/meta")
def meta():
    rows = corpus()
    evidence = json.loads((ROOT / "evidence.json").read_text(encoding="utf-8"))
    return {"network_enabled": True, "providers": provider_status(), "taxonomy": taxonomy(), "actions": {item["id"]: proposed_action(item["id"]) for item in taxonomy()}, "tool_plans": tool_routes()['plans'], "splits": {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}, "corpus_sha256": digest(), "evidence": evidence}


@app.get("/lab-api/cases")
def cases():
    return corpus()


@app.get('/lab-api/tool-routes')
def tool_routes():
    return {'plans': {item['id']: route_plan({'status': 'ok', 'intent': item['id']}, source='reference') for item in taxonomy()}}


@app.post("/lab-api/preview")
def preview(body: Preview):
    return request_preview([message.model_dump() for message in body.messages], body.language, body.instructions)


@app.post("/lab-api/classify")
def classify_case(body: Preview):
    if not provider_lock.acquire(blocking=False):
        raise HTTPException(409, detail="classification_running")
    try:
        return classify([message.model_dump() for message in body.messages], body.language, body.instructions)
    finally:
        provider_lock.release()


@app.get("/lab-api/originals")
def originals():
    path = storage.DATA_DIR / "original-transcripts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"source": "local_dataset", "conversations": []}


@app.post("/lab-api/benchmark")
def benchmark():
    global latest
    if not lock.acquire(blocking=False):
        raise HTTPException(409, detail="benchmark_running")
    try:
        latest = run_benchmark()
        return latest
    finally:
        lock.release()


@app.get("/lab-api/results")
def results():
    return latest


@app.get("/lab-api/health")
def health():
    return {"status": "ok", "external_calls": "jev_and_openai_on_explicit_run", "banking_actions": False}


app.include_router(editor_router)
# The /api prefix receives the bank's HttpOnly cookie, whose path is /api.
# Existing LAB-only links remain compatible and cannot access bank-bound runs without it.
app.include_router(editor_router,prefix='/api')

if (ROOT / "dist").exists():
    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="ui")
