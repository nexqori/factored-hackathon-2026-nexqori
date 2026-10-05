// Export existing local demo access without changing passwords or database rows.
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
if(process.argv.slice(2).join(' ')!=='--confirm-local'){
  console.error('Uso: node scripts/demo-access.mjs --confirm-local');process.exit(1);
}
try {
  const folder=resolve(root,'.local/ux-users/bryan-demo');
  const manifest=JSON.parse(readFileSync(resolve(folder,'manifest.private.json'),'utf8'));
  const records=JSON.parse(readFileSync(resolve(folder,'records.private.json'),'utf8'));
  const line=readFileSync(resolve(root,'.env'),'utf8').split(/\r?\n/).find(value=>value.startsWith('ADMIN_PASSWORD='));
  if(!line)throw new Error('Missing local password');
  let adminPassword=line.slice('ADMIN_PASSWORD='.length).trim();
  if((adminPassword.startsWith('"')&&adminPassword.endsWith('"'))||(adminPassword.startsWith("'")&&adminPassword.endsWith("'")))adminPassword=adminPassword.slice(1,-1);
  if(!adminPassword||records.users.length!==1)throw new Error('Invalid local configuration');
  const guide=resolve(folder,'ACCESOS.private.md');
  const ignored=spawnSync('git',['check-ignore','--quiet',guide],{cwd:root,windowsHide:true});
  if(ignored.status!==0)throw new Error('Output must remain ignored');
  const code=`import json,sys,os
from sqlalchemy import select
from sqlalchemy.engine import make_url
from backend.db import make_engine,make_sessions
from backend.models import User
from backend.security import verify
url=make_url(os.environ['DATABASE_URL'])
assert url.host=='db' and url.database=='nexqori'
body=json.load(sys.stdin)
with make_sessions(make_engine())() as db:
    customer=db.get(User,body['customerId'])
    admin=db.get(User,'nora')
    assert customer and customer.name=='Bryan' and customer.role=='customer'
    assert admin and admin.role=='admin'
    assert verify(body['customerPassword'],customer.password_hash)
    assert verify(body['adminPassword'],admin.password_hash)
    print(json.dumps({'customer':{'email':customer.email,'document':customer.identity_number},'admin':{'email':admin.email,'document':admin.identity_number}}))
`;
  const checked=spawnSync('docker',['compose','exec','-T','api','python','-c',code],{
    cwd:root,windowsHide:true,encoding:'utf8',timeout:30000,
    input:JSON.stringify({customerId:records.users[0].userId,customerPassword:manifest.password,adminPassword})});
  if(checked.status!==0)throw new Error('Stored credentials differ or API unavailable');
  const users=JSON.parse(checked.stdout);
  mkdirSync(folder,{recursive:true});
  writeFileSync(guide,[
    '# Accesos locales de prueba','', 'Banco: http://localhost:5180','',
    '## Bryan', '', 'Correo: '+users.customer.email, 'Documento: '+users.customer.document,
    'Contraseña: '+manifest.password,'',
    '## Administración','', 'Correo: '+users.admin.email,'Documento: '+users.admin.document,
    'Contraseña: '+adminPassword,'', 'Panel: http://localhost:5180/admin/complaints','',
    'Credenciales verificadas contra los hashes de esta instalación. No se cambiaron contraseñas ni datos.',
    'Usa otro perfil del navegador para abrir administración y cliente al mismo tiempo.',
    'Este archivo es privado. No lo subas a GitHub ni lo incluyas en capturas del pitch.',''
  ].join('\n'),{mode:0o600});
  console.log(JSON.stringify({verified:true,databaseChanged:false,guide},null,2));
} catch {
  console.error('No se exportaron accesos. Prepara Bryan y comprueba Docker y las contraseñas locales; no se cambió ningún acceso.');
  process.exit(1);
}
