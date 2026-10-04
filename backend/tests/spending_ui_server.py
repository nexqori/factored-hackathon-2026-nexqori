"""Explicit isolated fixture server for browser checks; never deployed."""
import json
import os
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.db import make_engine, make_sessions
from backend.main import create_app
from backend.models import Base, User
from backend.security import hasher
import secrets
from backend.ux_fixtures import ensure_pack, manifest_plan
from backend.spending_scenarios import ensure_spending_cases
from backend.tests.test_ux_fixtures import manifest

if os.getenv('NEXQORI_SPENDING_UI_CHECK')!='1':raise RuntimeError('Isolated check required')
folder=Path(os.environ['NEXQORI_SPENDING_UI_DATA']).resolve()
if not folder.is_relative_to(Path('.local/verification').resolve()):raise RuntimeError('Private directory required')
database=folder/'bank.sqlite'
if database.exists():raise RuntimeError('Fresh database required')
engine=make_engine('sqlite:///'+str(database));Base.metadata.create_all(engine)
pack=manifest();person=manifest_plan(pack)[0]
admin={'email':'tariffs-admin@example.com','password':secrets.token_urlsafe(24)}
with make_sessions(engine)() as db:
    ensure_pack(db,pack);scenario=ensure_spending_cases(db,person);db.commit()
    db.add(User(id='tariffs-admin',name='Verificación tarifas',email=admin['email'],password_hash=hasher.hash(admin['password']),role='admin',locale='es'));db.commit()
(folder/'credentials.private.json').write_text(json.dumps({'email':person['email'],'password':pack['passwords']['cargo'],'scenarios':scenario,'admin':admin}),encoding='utf-8')
os.environ['PROVIDER_EXAMPLES_ENABLED']='true'
os.environ['PROVIDER_EXAMPLES_CACHE']=str(folder/'sources.json')
app=create_app(engine,['http://127.0.0.1:5195'],False,login_limit=30)
app.mount('/assets',StaticFiles(directory='dist/assets'))
@app.get('/{path:path}')
def frontend(path:str):
    root=Path('dist').resolve();candidate=(root/path).resolve()
    return FileResponse(candidate if candidate.is_relative_to(root) and candidate.is_file() else root/'index.html')
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=5195,access_log=False)
