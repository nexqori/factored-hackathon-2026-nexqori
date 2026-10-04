"""Explicit isolated harness, reuses controlled chat and adds one test administrator."""
import json
import secrets
from uuid import uuid4
from backend.tests.chat_ui_server import app, engine, folder
from backend.db import make_sessions
from backend.models import User
from backend.security import hasher

person = {'email': uuid4().hex + '@nexqori.com', 'password': secrets.token_urlsafe(24)}
with make_sessions(engine)() as db:
    db.add(User(id=uuid4().hex, email=person['email'], password_hash=hasher.hash(person['password']),
                name='Verificación de formularios', role='admin', locale='es'))
    db.commit()
(folder / 'admin.private.json').write_text(json.dumps(person), encoding='utf-8')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5192, access_log=False)
