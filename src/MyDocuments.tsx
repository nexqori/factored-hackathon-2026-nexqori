import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileText } from 'lucide-react';
import { api, ApiError } from './api';
import { Dialog } from './components';
import { DocumentDownload } from './ChatDocuments';
import type { DocumentMeta } from './types';
import './documents.css';

type DocumentPage = {documents:DocumentMeta[];nextOffset:number|null;selected:DocumentMeta|null};

export function MyDocuments() {
  const {t}=useTranslation();const {search}=useLocation();const selected=new URLSearchParams(search).get('document');
  const [rows,setRows]=useState<DocumentMeta[]>([]);const [next,setNext]=useState<number|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [detail,setDetail]=useState<DocumentMeta|null>(null);
  const controller=useRef<AbortController|null>(null);const heading=useRef<HTMLHeadingElement>(null);const lastOffset=useRef(0);
  async function load(offset=0) {
    controller.current?.abort();const abort=new AbortController();controller.current=abort;lastOffset.current=offset;setBusy(true);setError('');
    try {const r=await api<DocumentPage>('/documents?offset='+offset+(selected?'&selected='+encodeURIComponent(selected):''),'GET',undefined,abort.signal);
      setRows(old=>{const all=[...(offset?old:[]),...(offset===0&&r.selected?[r.selected]:[]),...r.documents];return [...new Map(all.map(d=>[d.id,d])).values()];});setNext(r.nextOffset);
      if(offset===0&&selected)heading.current?.focus();
    } catch(e){if(!abort.signal.aborted)setError('error.'+(e instanceof ApiError?e.code:'generic'));}
    finally {if(!abort.signal.aborted)setBusy(false);}
  }
  useEffect(()=>{void load();return()=>controller.current?.abort();},[selected]);
  function summary(d:DocumentMeta) {return d.details.accountLast4?t('ending')+' •••• '+d.details.accountLast4:d.details.requestId||t(d.kind==='claims_summary'?'documents.allClaims':d.kind==='requests_summary'?'documents.allRequests':'documents.allProducts');}
  return <section className="requested-documents" aria-labelledby="requested-documents-title" aria-busy={busy}>
    <h2 id="requested-documents-title" ref={heading} tabIndex={-1}><FileText size={22} aria-hidden="true"/>{t('documents.requested')}</h2>
    <p className="muted">{t('documents.requestedHint')}</p>
    {!busy&&!rows.length&&!error&&<p className="empty-panel">{t('documents.empty')}</p>}
    <div className="requested-document-grid">{rows.map(d=><article key={d.id} data-document-request-id={d.id} className={'requested-document'+(d.id===selected?' selected':'')}>
      <span className="document-ready">{t('documents.statusReady')}</span><DocumentDownload document={d}/><p>{summary(d)}</p>
      <button className="button secondary" onClick={()=>setDetail(d)}>{t('documents.viewDetails')}</button>
    </article>)}</div>
    {error&&<div role="alert"><p>{t(error)}</p><button className="button secondary" onClick={()=>void load(lastOffset.current)}>{t('retry')}</button></div>}
    {busy&&<p role="status">{t('loading')}</p>}
    {next!==null&&!error&&<button className="button secondary" disabled={busy} onClick={()=>void load(next)}>{t('documents.more')}</button>}
    {detail&&<Dialog title={t('documents.viewDetails')} onClose={()=>setDetail(null)}><DocumentDownload document={detail}/><dl className="document-summary">
      <dt>{t('documents.scope')}</dt><dd>{summary(detail)}</dd>
      {detail.kind==='statement'&&<><dt>{t('documents.period')}</dt><dd>{detail.details.allHistory?t('documents.allHistory'):detail.details.startDate+' — '+detail.details.endDate}</dd></>}
      <dt>{t('documents.records')}</dt><dd>{detail.details.recordCount}</dd><dt>{t('language')}</dt><dd>{{es:'Español',en:'English',pt:'Português'}[detail.locale]}</dd>
    </dl><p className="muted">{t('documents.snapshot')}</p></Dialog>}
  </section>;
}
