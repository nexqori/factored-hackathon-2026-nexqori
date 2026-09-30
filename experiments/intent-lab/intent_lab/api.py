from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
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
        # Limit bodies, including chunked requests; no raw text is logged or persisted.
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
    return {"network_enabled": True, "providers": provider_status(), "taxonomy": taxonomy(), "actions": {item["id"]: proposed_action(item["id"]) for item in taxonomy()}, "splits": {split: sum(row["split"] == split for row in rows) for split in ("train", "validation", "test")}, "corpus_sha256": digest(), "evidence": evidence}


@app.get("/lab-api/cases")
def cases():
    return corpus()


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
    return {"status": "ok", "external_calls": "jev_on_explicit_run", "banking_actions": False}


if (ROOT / "dist").exists():
    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="ui")
