import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';
import { Search, FileDown } from 'lucide-react';
import { TransactionList } from './components';
import type { Dashboard, Transaction } from './types';
import { validDate } from './navigation';
import { filterMovements } from './movementFilters';
import './documents.css';

export function Movements({data,onSelect}:{data:Dashboard;onSelect:(tx:Transaction)=>void}){
  const {t}=useTranslation();const [params,setParams]=useSearchParams();const rows=filterMovements(data.transactions,params);
  function change(key:string,value:string){setParams(old=>{const next=new URLSearchParams(old);if(value)next.set(key,value);else next.delete(key);return next;});}
  const start=params.get('start')||'',end=params.get('end')||'';
  const invalid=!!(start&&!validDate(start)||end&&!validDate(end)||start&&end&&start>end);
  return <><div className="page-heading"><h1>{t('movements')}</h1><p>{t('activityNote')}</p><Link className="text-link" to="/documents"><FileDown size={18} aria-hidden="true"/>{t('documents.open')}</Link></div>
    <div className="movement-filters">
      <label className="search-field"><Search size={19} aria-hidden="true"/><span className="sr-only">{t('search')}</span><input type="search" placeholder={t('search')} value={params.get('q')||''} onChange={e=>change('q',e.target.value)}/></label>
      <label>{t('product')}<select value={params.get('product')||''} onChange={e=>change('product',e.target.value)}><option value="">{t('documents.allProducts')}</option>{data.products.map(p=><option key={p.id} value={p.id}>{t(p.type)} · •••• {p.last4}</option>)}</select></label>
      <label>{t('status')}<select value={params.get('status')||'all'} onChange={e=>change('status',e.target.value)}>{['all','completed','pending','declined'].map(s=><option key={s} value={s}>{t(s)}</option>)}</select></label>
      <label>{t('documents.from')}<input type="date" value={start} max={end||undefined} aria-invalid={invalid} onChange={e=>change('start',e.target.value)}/></label>
      <label>{t('documents.to')}<input type="date" value={end} min={start||undefined} aria-invalid={invalid} onChange={e=>change('end',e.target.value)}/></label>
      <button className="button secondary" onClick={()=>setParams({})}>{t('clear')}</button>
    </div>
    {invalid&&<p role="alert">{t('movements.invalidPeriod')}</p>}
    <p className="muted" role="status">{t('movements.results',{count:rows.length})}</p>
    <section className="panel transaction-panel"><TransactionList rows={rows} products={data.products} onSelect={onSelect}/>{!rows.length&&<p className="empty-panel">{t('noResults')}</p>}</section></>;
}
