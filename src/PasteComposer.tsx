import { useState, type ClipboardEvent } from 'react';
import { FileText, Send, X } from 'lucide-react';
import './paste-composer.css';

type Copy = { text:string; preview:string; remove:string; placeholder:string; label:string; send:string; limit:string; failed:string };
export function PasteComposer({ copy, busy=false, limit=8000, onSend }: { copy:Copy; busy?:boolean; limit?:number; onSend:(message:string,pastedText:string)=>Promise<unknown> }) {
  const [draft,setDraft]=useState(''); const [pasted,setPasted]=useState(''); const [error,setError]=useState('');
  const length=draft.length+pasted.length;
  function paste(event:ClipboardEvent<HTMLTextAreaElement>){
    const value=event.clipboardData.getData('text/plain');
    if(value.length<200&&value.split('\n').length<4) return;
    event.preventDefault();
    const next=pasted?pasted+'\n\n'+value:value;
    if(next.length+draft.length>limit){setError(copy.limit);return;}
    setPasted(next);setError('');
  }
  async function submit(){
    if(busy||length>limit||(!draft.trim()&&!pasted.trim()))return;
    setError('');
    try{await onSend(draft.trim(),pasted);setDraft('');setPasted('');}catch{setError(copy.failed);}
  }
  return <form className="paste-composer" onSubmit={e=>{e.preventDefault();void submit();}}>
    {pasted&&<div className="pasted-card"><FileText size={22} aria-hidden="true"/><details><summary><strong>{pasted.trim().split('\n')[0].slice(0,45)||copy.text}</strong><span>{copy.text} · {pasted.length.toLocaleString()}</span><span className="sr-only">{copy.preview}</span></summary><pre tabIndex={0}>{pasted}</pre></details><button className="paste-remove" type="button" disabled={busy} aria-label={copy.remove} onClick={()=>{setPasted('');setError('');}}><X size={16}/></button></div>}
    <div className="paste-entry"><textarea data-assistant-input rows={2} aria-label={copy.label} placeholder={copy.placeholder} value={draft} maxLength={limit} disabled={busy} onPaste={paste} onChange={e=>{setDraft(e.target.value);setError('');}} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void submit();}}}/><button type="submit" disabled={busy||length>limit||(!draft.trim()&&!pasted.trim())} aria-label={copy.send}><Send size={18}/></button></div>
    {(error||length>limit)&&<p role="alert" className="error-text">{error||copy.limit}</p>}
  </form>;
}
