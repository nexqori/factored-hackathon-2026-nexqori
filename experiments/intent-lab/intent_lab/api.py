from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Query
from uuid import UUID
from fastapi.responses import JSONResponse
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

app = FastAPI(title="Nexqori · Intent Lab", docs_url="/lab-api/docs", redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
lock = threading.Lock()
provider_lock = threading.Lock()
latest = None


@app.middleware("http")
async def local_only(request: Request, call_next):
    if request.method in ("POST", "PUT"):
        if request.headers.get("origin") not in (None, "http://localhost:5190", "http://127.0.0.1:5190", "http://localhost:5191", "http://127.0.0.1:5191"):
            return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
        # Provider inputs are saved only in private local run records.
        if len(await request.body()) > 24000:
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
            rows.append({k:result.get(k) for k in ('id','created_at','thread_id')}|{'kind':record.get('kind','classification'),'actor':record.get('actor','local_operator'),'intent':result.get('jev',{}).get('intent'),'jev_status':result.get('jev',{}).get('status'),'llm_status':result.get('llm',{}).get('status')})
        except (ValueError,KeyError): continue
    return {'runs':rows,'nextOffset':offset+30 if len(paths)>offset+30 else None}

@app.get('/lab-api/runs/{run_id}')
def run_detail(run_id: UUID):
    path=storage.DATA_DIR/'runs'/f'{run_id}.json'
    if not path.exists(): raise HTTPException(404,'not_found')
    return json.loads(path.read_text(encoding='utf-8'))


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


if (ROOT / "dist").exists():
    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="ui")
