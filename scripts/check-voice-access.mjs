// Read-only provider preflight. The API key stays inside the API container.
import {spawnSync} from 'node:child_process';
const code = `
import json,os,sys,httpx
key=os.getenv('OPENAI_LIVE_API_KEY') or os.getenv('LLM_API_KEY','')
result={'model':'gpt-live-1','configured':bool(key),'available':False}
if key:
    try:
        response=httpx.get('https://api.openai.com/v1/models/gpt-live-1',headers={'Authorization':'Bearer '+key},timeout=15)
        result['status']=response.status_code
        result['available']=response.status_code==200 and response.json().get('id')=='gpt-live-1'
    except (httpx.HTTPError,ValueError):
        result['status']='connection_or_response_error'
print(json.dumps(result))
sys.exit(0 if result['available'] else 1)
`;
const result=spawnSync('docker',['compose','exec','-T','api','python','-'],{
  input:code,encoding:'utf8',windowsHide:true,timeout:25000,maxBuffer:65536,
});
if(result.stdout)process.stdout.write(result.stdout);
if(result.error||!result.stdout)console.error('No se pudo comprobar el acceso. Revisa Docker y la conexión.');
process.exit(result.status===0?0:1);
