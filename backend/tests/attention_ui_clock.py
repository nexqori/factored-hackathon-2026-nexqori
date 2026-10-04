"""Advance closure evaluation only for the fresh, isolated UI database."""
import sys
from pathlib import Path
from sqlalchemy import select
from backend.db import make_engine, make_sessions
from backend.models import AttentionReview
from backend.attention import process_due

path = Path(sys.argv[1]).resolve()
if not path.is_relative_to(Path('.local/verification').resolve()) or path.name != 'bank.sqlite':
    raise RuntimeError('Isolated UI database required')
engine = make_engine('sqlite:///' + str(path))
sessions = make_sessions(engine)
with sessions() as db:
    row = db.scalar(select(AttentionReview).where(AttentionReview.request_id == sys.argv[2]))
    if row is None:
        raise RuntimeError('Expected isolated attention review')
    deadline = row.due_at
assert process_due(sessions, deadline) == 1
engine.dispose()
