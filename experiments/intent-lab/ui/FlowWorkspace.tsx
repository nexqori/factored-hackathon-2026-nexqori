import {useState} from 'react';
import {FlowLabPanel} from './FlowLabPanel';
import {WorkflowEditor} from './WorkflowEditor';
import {et} from './editorLocales';
import type {Language} from './locales';

export function FlowWorkspace({language}:{language:Language}){
  const [mode,setMode]=useState<'editor'|'inspector'>(()=>new URLSearchParams(location.search).get('mode')==='editor'?'editor':new URLSearchParams(location.search).get('mode')==='inspector'||new URLSearchParams(location.search).has('run')?'inspector':'editor');
  return <div className={'flow-workspace-shell '+mode+'-mode'}><div className="flow-mode-tabs" role="group" aria-label={et(language,'editor')}><button aria-pressed={mode==='editor'} onClick={()=>setMode('editor')}>{et(language,'editor')}</button><button aria-pressed={mode==='inspector'} onClick={()=>setMode('inspector')}>{et(language,'inspector')}</button></div><div hidden={mode!=='editor'}><WorkflowEditor language={language}/></div>{mode==='inspector'&&<FlowLabPanel key={language} language={language}/>}</div>;
}
