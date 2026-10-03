import {randomBytes, createHash} from 'node:crypto';
import {readFile, writeFile, readdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
const names=['LAB_DB_PASSWORD','TARGET_DB_PASSWORD','TARGET_CUSTOMER_PASSWORD','TARGET_SECOND_PASSWORD','TARGET_ADMIN_PASSWORD'];
try {
  await writeFile(path.join(root,'.env'),names.map(n=>`${n}=${randomBytes(32).toString('hex')}`).join('\n')+'\n',{flag:'wx',mode:0o600});
  console.log('Created local service secrets. No administrator password is generated.');
} catch(e) { if(e.code!=='EEXIST') throw e; console.log('Existing .env preserved.'); }
async function hashTree(base,folders) {
  const hash=createHash('sha256');
  async function walk(dir) {
    for(const entry of (await readdir(dir,{withFileTypes:true})).sort((a,b)=>a.name.localeCompare(b.name))) {
      if(['__pycache__','.pytest_cache','private','node_modules'].includes(entry.name))continue;
      const p=path.join(dir,entry.name);
      if(entry.isDirectory())await walk(p);
      else if(/\.(py|json|lock|ini|ts|tsx|css|mjs|yaml|conf)$/.test(p) && entry.name!=='build.json') {hash.update(path.relative(base,p));hash.update(await readFile(p));}
    }
  }
  for(const folder of folders)await walk(path.join(base,folder));
  return hash.digest('hex');
}
await writeFile(path.join(root,'lab/build.json'),JSON.stringify({code:await hashTree(root,['lab','src','migrations','scripts']),target:await hashTree(path.join(root,'..'),['backend','chat-agente/nexqori_chat','chat-agente/config','chat-agente/templates']),fixtures:createHash('sha256').update(await readFile(path.join(root,'../backend/seed.py'))).digest('hex')},null,2)+'\n');
console.log('Recorded source hashes. Run setup again before rebuilding changed code.');
