"""Small local JSON store. No database, cloud sync, or benchmark split mutation."""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .data import ROOT

DATA_DIR = Path(os.environ.get("NEXQORI_LAB_DATA", str(ROOT.parents[1] / ".local" / "intent-lab")))
_lock = threading.Lock()


def read_conversations():
    path = DATA_DIR / "conversations.json"
    if not path.exists():
        return {"version": 1, "conversations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_conversation(body, conversation_id=None):
    with _lock:
        document = read_conversations()
        rows = document["conversations"]
        existing = next((row for row in rows if row["id"] == conversation_id), None)
        if conversation_id is not None and existing is None:
            raise KeyError("conversation_not_found")
        if existing is None and len(rows) >= 100:
            raise ValueError("conversation_limit")
        saved = {**body, "id": existing["id"] if existing else str(uuid.uuid4()), "source": "custom_local", "review": "pending", "updated_at": datetime.now(timezone.utc).isoformat()}
        if existing is not None:
            rows[rows.index(existing)] = saved
        else:
            rows.append(saved)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temporary = DATA_DIR / "conversations.json.tmp"
        temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(DATA_DIR / "conversations.json")
        return saved
