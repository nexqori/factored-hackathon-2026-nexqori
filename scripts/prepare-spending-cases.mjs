// Add only: no reset, deletion or HTTP maintenance endpoint is shipped.
import {readFileSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
const args=process.argv.slice(2);
if(!args.includes('--confirm-local')||args.some(a=>a!=='--confirm-local'&&!a.startsWith('--pack=')))throw new Error('Uso: node scripts/prepare-spending-cases.mjs --confirm-local --pack=equipo-ux');
const pack=args.find(a=>a.startsWith('--pack='))?.slice(7)||'equipo-ux';
if(!/^[a-z0-9][a-z0-9-]{0,39}$/.test(pack))throw new Error('Paquete inválido');
const folder=resolve('.local/ux-users',pack);const manifest=JSON.parse(readFileSync(resolve(folder,'manifest.private.json'),'utf8'));
if(manifest.packId!==pack)throw new Error('Paquete inconsistente');
const child=spawnSync('docker',['compose','exec','-T','-e','NEXQORI_LOCAL_VERIFY=1','api','python','-m','backend.spending_scenarios'],{input:JSON.stringify(manifest),encoding:'utf8',windowsHide:true,timeout:120000});
if(child.status!==0)throw new Error('No se añadieron los casos. Comprueba la versión de la API y la consistencia del paquete.');
const result=JSON.parse(child.stdout);writeFileSync(resolve(folder,'spending.private.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify({created:result.created,transactions:result.transactionIds,guide:'docs/casos-tendencias-camila.md'}));
