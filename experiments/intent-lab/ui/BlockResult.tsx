import type {Language} from './locales';
import {et,type EditorKey} from './editorLocales';
import {fieldTitle} from './flowLocales';
import {ActivationPlan} from './ActivationPlan';
import type {Trace,Graph,CaseDefinition,Activation} from './workflowGraph';
type Fact={field:string;value:string;quote?:string;source?:string;reference_id?:string;audit_event_id?:string;observed_at?:string};
type BankRead={tool:string;auditEventId:string;observed_at:string;data:{transaction?:{id:string;merchant:string;amountMinor:number;currency:string;date:string;status:string};request?:{id:string;status:string}|null;events?:{action:string;at:string}[]}};
type Output={reference?:string;events?:{event:string;timestamp:string}[];family?:string;intent?:string;probabilities?:Record<string,number>;port?:string;matched?:boolean;predicate?:string;reply?:string;state?:string;assessment?:string;messages?:{role:string;content:string}[];required_fields?:string[];missing_fields?:string[];observations?:Fact[];verified_facts?:Fact[];customer_questions?:{field:string;text:string}[];questions?:{field:string;text:string}[];would_activate?:Activation[];contract?:{steps:string[]};reference_context?:{status:string};bank_evidence?:{status:string;error?:string;reads:BankRead[];missing_references:string[]};error?:string};
export function BlockResult({row,graph,language,cases,waiting,respond,configure}:{row:Trace;graph:Graph;language:Language;cases:CaseDefinition[];waiting:boolean;respond:()=>void;configure:()=>void}){
 const t=(key:EditorKey)=>et(language,key),out=row.output as Output;
 const field=(key:string)=>key==='transaction_id'||key==='request_id'?t(key):fieldTitle(language,key);
 const target=graph.edges.find(e=>e.source===row.node_id&&e.port===(out.port||'next'))?.target;
 const title=out.intent?cases.find(c=>c.intent===out.intent)?.title:out.family&&t(out.family as EditorKey);
 const questions=out.customer_questions||out.questions||[];
 function display(item:Fact){
  if(item.source!=='nexqori_records')return item.value||item.quote;
  if(item.field==='date'&&!Number.isNaN(Date.parse(item.value)))return new Date(item.value).toLocaleString(language);
  if(item.field==='status'&&['pending','completed','rejected'].includes(item.value))return t(('bank_status_'+item.value) as EditorKey);
  if(item.field==='amount'){const match=item.value.match(/^(-?\d+(?:\.\d+)?) ([A-Z]{3})$/);if(match)return new Intl.NumberFormat(language,{style:'currency',currency:match[2]}).format(Number(match[1]));}
  return item.reference_id?item.value.replace(' · '+item.reference_id,''):item.value;
 }
 function facts(items:Fact[],label:EditorKey){return items.length>0&&<section><h3>{t(label)}</h3><dl className="result-facts">{items.map((item,i)=><div key={i}><dt>{field(item.field)}</dt><dd>{display(item)}{item.quote&&item.value&&item.value!==item.quote&&<q>{item.quote}</q>}{item.reference_id&&<small>{item.reference_id}</small>}</dd></div>)}</dl></section>;}
 return <div className="block-result" data-simple-result={row.node_id}>
 {out.error&&<p role="alert">{t(out.error.startsWith('bank_')?out.error as EditorKey:'error')}</p>}
 {title&&<section className="result-decision"><span>{t('resultDecision')}</span><h3>{title}</h3>{out.probabilities&&<small>{t('resultProbability')}: {new Intl.NumberFormat(language,{style:'percent',maximumFractionDigits:1}).format(out.probabilities[out.intent||out.family||'']||0)}</small>}</section>}
 {out.messages&&<section><h3>{t('resultReceived')}</h3><p className="result-quote">{out.messages.filter(m=>m.role==='user').at(-1)?.content}</p></section>}
 {out.reference&&<section><h3>{t(row.kind==='notify'?'localNotice':'localIncident')}</h3><p>{out.reference}</p>{out.events&&<ul>{out.events.map((event,i)=><li key={i}>{t(event.event as EditorKey)} · {new Date(event.timestamp).toLocaleString(language)}</li>)}</ul>}</section>}
 {out.matched!==undefined&&<p className="result-decision">{t(out.matched?'branchYes':'branchNo')} · {t(out.predicate as EditorKey)}</p>}
 {out.contract&&<section><h3>{t('procedure')}</h3><ol>{out.contract.steps.map((s,i)=><li key={i}>{s}</li>)}</ol></section>}
 {out.required_fields&&row.kind==='contract'&&<p>{t('needed')}: {out.required_fields.map(field).join(' · ')}</p>}
 {out.assessment&&<section><h3>{t('resultAssessment')}</h3><p>{t(('assessment_'+out.assessment) as EditorKey)}</p></section>}
 {facts(out.verified_facts||[],'resultVerified')}{facts(out.observations||[],'resultDeclared')}
 {row.kind==='context'&&<>
 {out.missing_fields?.length?<section><h3>{t('resultMissing')}</h3><ul>{out.missing_fields.map(f=><li key={f}>{field(f)}</li>)}</ul></section>:row.status==='ok'&&<p className="result-complete">{t('resultAllFields')}</p>}
 <section><h3>{t('resultSources')}</h3>{out.bank_evidence?.reads?.length?out.bank_evidence.reads.map((read,i)=><article className="bank-read" key={i}><strong>{cases.flatMap(c=>c.tool_plan.tools).find(tool=>tool.id===read.tool)?.titles[language]||read.tool}</strong><small>{t('bankAudit')}: {read.auditEventId}</small><small>{t('bankReadAt')}: {new Date(read.observed_at).toLocaleString(language)}</small>
 {read.data.transaction&&<p>{read.data.transaction.merchant} · {read.data.transaction.status}<br/><code>{read.data.transaction.id}</code></p>}{read.data.request&&<p>{t('requestId')}: {read.data.request.id} · {read.data.request.status}</p>}
 {read.data.events&&<><h4>{t('bankLogs')}</h4>{read.data.events.length?<ul>{read.data.events.map((event,j)=><li key={j}>{event.action} · {new Date(event.at).toLocaleString(language)}</li>)}</ul>:<p>{t('bankNoLogs')}</p>}</>}</article>):<p>{t('resultBankPending')}</p>}<p className="editor-help">{t('bankLogLimit')}</p></section>
 <section><h3>{t('resultReference')}</h3><p>{t(out.reference_context?.status==='provided'?'resultReferenceUsed':'resultNoReference')}</p><button onClick={configure}>{t('contextSettings')}</button></section></>}
 {questions.length>0&&<section className="result-questions"><h3>{t('resultQuestions')}</h3>{questions.map((q,i)=><p key={i}>{q.text}</p>)}{waiting?<button data-respond-now onClick={respond}>{t('respondNow')}</button>:<p className="editor-help">{t('resultPausedQuestion')}</p>}</section>}
 {out.reply&&<p className="result-quote">{out.reply}</p>}
 {!!out.would_activate?.length&&<><h3>{t('pendingActions')}</h3><ActivationPlan items={out.would_activate} language={language}/></>}
 {target&&<p className="result-next">{t('resultNext')}: <strong>{graph.nodes.find(n=>n.id===target)?.label[language]}</strong></p>}
 <p className="editor-help">{t('resultNoAction')}</p>
 </div>;
}
