import { productLabelKey } from './productLabels';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { SpendingInsight, SpendingPage } from './SpendingTrend';
import { formatMoney } from './components';
import type { Locale } from './i18n';
import './spending.css';
import { TransactionList } from './components';
import type { Dashboard, Transaction } from './types';
import { validDate } from './navigation';
import { filterMovements } from './movementFilters';
import './documents.css';

export function Movements({data,onSelect}:{data:Dashboard;onSelect:(tx:Transaction)=>void}){
  const {t,i18n}=useTranslation();const [params,setParams]=useSearchParams();
  const [insights,setInsights]=useState<SpendingInsight[]>([]);const [next,setNext]=useState<number|null>(null);
  const [loading,setLoading]=useState(true);const [failed,setFailed]=useState(false);const [retry,setRetry]=useState(0);
  useEffect(()=>{const abort=new AbortController();setLoading(true);setFailed(false);setInsights([]);
    void api<SpendingPage>('/movements/trends','GET',undefined,abort.signal).then(r=>{setInsights(r.items);setNext(r.nextOffset);})
      .catch(()=>{if(!abort.signal.aborted)setFailed(true);}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});
    return ()=>abort.abort();},[data.transactions,retry]);
  async function more(){if(next===null||loading)return;setLoading(true);setFailed(false);try{const r=await api<SpendingPage>('/movements/trends?offset='+next);setInsights(old=>[...old,...r.items]);setNext(r.nextOffset);}catch{setFailed(true);}finally{setLoading(false);}}
  const rows=filterMovements(data.transactions,params,insights);
  const list=useRef<HTMLElement>(null);
  const focusedTransaction=useRef<string|null>(null);
  const selectedTransaction=params.get('transaction');
  useEffect(()=>{
    if(!selectedTransaction){focusedTransaction.current=null;return;}
    if(focusedTransaction.current===selectedTransaction)return;
    const frame=requestAnimationFrame(()=>{
      const row=Array.from(list.current?.querySelectorAll<HTMLElement>('[data-transaction-id]')||[])
        .find(el=>el.dataset.transactionId===selectedTransaction);
      if(row){row.scrollIntoView({block:'center',behavior:'instant'});focusedTransaction.current=selectedTransaction;}
    });
    return()=>cancelAnimationFrame(frame);
  },[selectedTransaction,data.transactions]);
  const unusual=insights.filter(i=>i.classification==='unusual');
  function change(key:string,value:string){setParams(old=>{const next=new URLSearchParams(old);if(value)next.set(key,value);else next.delete(key);return next;});}
  const start=params.get('start')||'',end=params.get('end')||'';
  const invalid=!!(start&&!validDate(start)||end&&!validDate(end)||start&&end&&start>end);
  return <div className="movements-page"><div className="page-heading"><h1>{t('movements')}</h1></div>
    {params.get('transaction')&&<p className="notice" role="status">{t('movements.assistantMatch')}</p>}
    {(params.get('category')||params.get('amountMinor'))&&<p className="muted">{t('movements.assistantFilters')}: {params.get('category')==='transfer'&&t('transfers')} {params.get('amountMinor')&&new Intl.NumberFormat(i18n.language,{minimumFractionDigits:2}).format(Number(params.get('amountMinor'))/100)}</p>}
    <div className="movement-filters">
      <label className="search-field"><Search size={19} aria-hidden="true"/><span className="sr-only">{t('search')}</span><input type="search" placeholder={t('search')} value={params.get('q')||''} onChange={e=>change('q',e.target.value)}/></label>
      <label>{t('product')}<select value={params.get('product')||''} onChange={e=>change('product',e.target.value)}><option value="">{t('documents.allProducts')}</option>{data.products.map(p=><option key={p.id} value={p.id}>{t(productLabelKey(p))} · •••• {p.last4}</option>)}</select></label>
      <label>{t('status')}<select aria-label={t('status')} value={params.get('status')||'all'} onChange={e=>change('status',e.target.value)}>{['all','completed','pending','declined'].map(s=><option key={s} value={s}>{t(s)}</option>)}</select></label>
    </div>
    <details className="movement-extra-filters" key={params.get('transaction')||'all'}>
      <summary>{t('movements.moreFilters')}{(start||end||params.get('trend')&&params.get('trend')!=='all')&&<span className="badge">{t('movements.filtersActive')}</span>}</summary>
      <div className="movement-filters">
      <label>{t('spending.filter')}<select aria-label={t('spending.filter')} value={params.get('trend')||'all'} onChange={e=>change('trend',e.target.value)}>{['all','unusual','comparable','limited','exceptional'].map(s=><option key={s} value={s}>{t(s==='all'?'all':'spending.'+s)}</option>)}</select></label>
      <label>{t('documents.from')}<input type="date" value={start} max={end||undefined} aria-invalid={invalid} onChange={e=>change('start',e.target.value)}/></label>
      <label>{t('documents.to')}<input type="date" value={end} min={start||undefined} aria-invalid={invalid} onChange={e=>change('end',e.target.value)}/></label>
      </div>
    </details>
    <div className="movement-results-bar"><p className="muted" role="status">{t('movements.results',{count:rows.length})}</p>
      {params.size>0&&<button className="text-link" onClick={()=>setParams({})}>{t('clear')}</button>}
    </div>
    {invalid&&<p role="alert">{t('movements.invalidPeriod')}</p>}
    <section className="panel transaction-panel" ref={list}><TransactionList highlightedId={params.get('transaction')} rows={rows} products={data.products} onSelect={onSelect}/>{!rows.length&&<p className="empty-panel">{t('noResults')}</p>}</section>
    <details className="spending-overview"><summary>{t('spending.title')}</summary><p>{t('spending.intro')}</p>
      <p className="muted" role="status">{t(loading?'loading':failed?'spending.error':'spending.coverage',{count:insights.length})}</p>
      {failed&&<button className="text-link" onClick={()=>setRetry(n=>n+1)}>{t('retry')}</button>}
      {!!unusual.length&&<div className="spending-highlights">{unusual.slice(0,3).map(i=>{const tx=data.transactions.find(r=>r.id===i.transactionId);return tx&&<button className="spending-highlight" key={tx.id} onClick={()=>onSelect(tx)}><small>{t('spending.unusual')}</small><strong>{tx.merchant} · {formatMoney(Math.abs(tx.amountMinor),i18n.language as Locale,tx.currency)}</strong><span>{t('spending.average')}: {formatMoney(i.comparison.averageMinor!,i18n.language as Locale,tx.currency)}</span><span>{t('spending.review')} →</span></button>;})}</div>}
      {next!==null&&<button className="text-link" disabled={loading} onClick={()=>void more()}>{t('spending.more')}</button>}
    </details>
  </div>;
}
