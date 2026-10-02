import {useState} from 'react';
import {CheckCircle2,Search} from 'lucide-react';
import type {Language} from './locales';
import {et} from './editorLocales';
import {fieldTitle} from './flowLocales';
import {caseInScope,type CaseDefinition} from './workflowGraph';

const families=['problem','query','service','clarification'] as const;
export function CaseTaxonomy({language,cases,scope,selected,probabilities}:{language:Language;cases:CaseDefinition[];scope:string;selected?:string;probabilities?:Record<string,number>}){
 const [search,setSearch]=useState(''),[onlyEligible,setOnlyEligible]=useState(false);
 const t=(key:Parameters<typeof et>[1])=>et(language,key);
 const eligible=cases.filter(item=>caseInScope(item,scope));
 const visible=cases.filter(item=>(!onlyEligible||caseInScope(item,scope))&&(item.title+' '+item.summary).toLocaleLowerCase(language).includes(search.toLocaleLowerCase(language)));
 return <section className="case-taxonomy" aria-label={t('caseCatalog')}>
  <h3>{t('caseCatalog')} <span>{cases.length}</span></h3><p className="editor-help">{t('catalogHint')}</p>
  <div className="catalog-filters" role="group" aria-label={t('scope')}><button aria-pressed={!onlyEligible} onClick={()=>setOnlyEligible(false)}>{t('all')} · {cases.length}</button><button aria-pressed={onlyEligible} onClick={()=>setOnlyEligible(true)}>{t('thisBlock')} · {eligible.length}</button></div>
  <label className="editor-search"><Search size={14}/><input aria-label={t('searchCases')} placeholder={t('searchCases')} value={search} onChange={e=>setSearch(e.target.value)}/></label>
  {families.map(family=>{const items=visible.filter(item=>item.family===family);return items.length>0&&<section className="taxonomy-group" data-case-family={family} key={family}>
   <h4>{t(('family_'+family) as 'family_problem')} <span>{items.length}</span></h4>
   {items.map(item=><details key={item.intent} data-classification-case={item.intent} className={'taxonomy-case '+(item.intent===selected?'is-classified ':'')+(caseInScope(item,scope)?'eligible':'other-route')}>
    <summary><span>{item.intent===selected&&<CheckCircle2 size={14} aria-label={t('selectedClassification')}/>}<strong>{item.title}</strong></span><small>{item.intent===selected?t('selectedClassification'):t(caseInScope(item,scope)?'thisBlock':'otherBranch')}{typeof probabilities?.[item.intent]==='number'?' · '+new Intl.NumberFormat(language,{style:'percent',maximumFractionDigits:1}).format(probabilities[item.intent]):''}</small></summary>
    <p>{item.summary}</p><p className="taxonomy-route">{t('derivesTo')}: {t(item.family==='problem'?'contract':item.family==='clarification'?'otherwise':'query')}</p>
    <h5>{t('needed')}</h5><p>{item.fields.map(field=>fieldTitle(language,field)).join(' · ')||t('noExtraFields')}</p>
    {item.contract&&<><h5>{t('procedure')}</h5><ol>{item.contract.steps.map((step,i)=><li key={i}>{step}</li>)}</ol></>}
    <h5>{t('pendingActions')}</h5><ul>{item.tool_plan.tools.map(tool=><li key={tool.id}>{tool.titles[language]}</li>)}</ul>
   </details>)}
  </section>;})}
  {!visible.length&&<p>{t('noneFound')}</p>}
 </section>;
}
