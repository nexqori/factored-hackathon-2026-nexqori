import {useState} from 'react';
import type {Language} from './locales';
import {et,type EditorKey} from './editorLocales';
export type BankSelection={transaction_id:string|null;request_id:string|null};
export type BankBinding=BankSelection&{owner_id:string};
type Transaction={id:string;merchant:string;amountMinor:number;currency:string;date:string;status:string};
type Records={user:{id:string;name:string};transactions:Transaction[];hasMore:boolean;auditEventId:string};
export function BankContextPanel({language,selection,onChange,binding,locked=false}:{language:Language;selection:BankSelection|null;onChange:(v:BankSelection|null)=>void;binding?:BankBinding|null;locked?:boolean}){
 const t=(key:EditorKey)=>et(language,key),[records,setRecords]=useState<Records|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState<EditorKey|null>(null);
 async function connect(){setBusy(true);setError(null);try{const r=await fetch('/api/lab-api/editor/bank/records?language='+language,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});const value=await r.json();if(!r.ok)throw new Error(value.detail);if(binding&&value.user.id!==binding.owner_id)throw new Error('bank_reference_unavailable');setRecords(value);if(!selection&&!locked)onChange({transaction_id:null,request_id:null});}catch(e){const code=e instanceof Error?e.message:'';setError((['bank_session_required','bank_customer_required','bank_reference_unavailable','bank_read_forbidden'].includes(code)?code:'bank_unavailable') as EditorKey);}finally{setBusy(false);}}
 return <section className="bank-context" data-bank-panel><h3>{t('bankRecords')}</h3><p className="editor-help">{t('bankHint')}</p>
 <div className="button-row"><button data-bank-connect disabled={busy} onClick={()=>void connect()}>{t('bankConnect')}</button><a href={'http://'+location.hostname+':5180/'} target="_blank" rel="noreferrer">{t('bankOpen')}</a></div>
 {error&&<p role="alert">{t(error)}</p>}{records&&<><p><strong>{t('bankOwner')}: {records.user.name}</strong></p><p className="editor-help">{t('bankOwn')} {t('bankLimit')}</p></>}
 {(records||binding)&&<><label className="bank-toggle"><input type="checkbox" checked={!!selection} disabled={locked||!!binding} onChange={e=>onChange(e.target.checked?{transaction_id:null,request_id:null}:null)}/>{t('bankEnabled')}</label>
 {selection&&<><label>{t('transaction_id')}<select data-bank-transaction disabled={locked||!records} value={selection.transaction_id||''} onChange={e=>onChange({...selection,transaction_id:e.target.value||null,request_id:null})}><option value="">{t('bankChoose')}</option>{selection.transaction_id&&!records?.transactions.some(v=>v.id===selection.transaction_id)&&<option value={selection.transaction_id}>{selection.transaction_id}</option>}{records?.transactions.map(tx=><option key={tx.id} value={tx.id}>{tx.merchant} · {new Intl.NumberFormat(language,{style:'currency',currency:tx.currency}).format(tx.amountMinor/100)} · {tx.date} · {tx.status}</option>)}</select></label>
 <label>{t('request_id')}<input data-bank-request maxLength={64} disabled={locked} value={selection.request_id||''} onChange={e=>onChange({...selection,request_id:e.target.value.trim()||null})}/></label><small>{t(binding?'bankUpdate':'bankNoMatch')}</small></>}
 </>}{binding&&<p className="editor-help">{t('bankLinked')} · <code>{binding.transaction_id||binding.request_id||'—'}</code></p>}
 </section>;
}
