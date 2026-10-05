import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ChevronLeft, ChevronRight, FileSearch, RefreshCw, Search } from 'lucide-react';
import { ClaimTrace } from './ClaimTrace';
import { RequestStatus } from './RequestProgress';
import { serviceTitle } from './catalog';
import type { Locale } from './i18n';
import type { RequestCase, User } from './types';
import './admin-inbox.css';

export function AdminClaimsPanel({ users, requests, onRefresh }: { users: User[]; requests: RequestCase[]; onRefresh?: () => Promise<unknown> }) {
  const { t, i18n } = useTranslation(); const [params, setParams] = useSearchParams();
  const [busy, setBusy] = useState(false); const [error, setError] = useState(false); const [revision, setRevision] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const rows = useRef<HTMLDivElement>(null); const [pageSize, setPageSize] = useState(5);
  useEffect(() => {
    const element = rows.current; if (!element) return;
    const observer = new ResizeObserver(() => {
      if (element.clientHeight === 0) return;
      setPageSize(window.matchMedia('(max-width:850px)').matches ? 5 : Math.max(1, Math.min(5, Math.floor((element.clientHeight - 16) / 100))));
    });
    observer.observe(element); return () => observer.disconnect();
  }, []);
  const user = params.get('user') || ''; const query = params.get('q') || ''; const status = params.get('status') || 'all';
  const cases = requests.filter(r => r.kind === 'claim' && (!user || r.userId === user));
  const stage = (r: RequestCase) => r.refund?.creditTransactionId ? 'refunded' : r.handling?.stage || (r.status === 'in_review' ? 'in_review' : 'received');
  const matches = cases.filter(r => (status === 'all' || (status.startsWith('refund_') ? r.refund?.status === status.slice(7) : status === 'handed_off' ? r.status === status : stage(r) === status)) && [r.id, r.customerName, r.details, r.transactionId, r.refund?.id, r.refund?.creditTransactionId].some(value => value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())));
  const pages = Math.max(1, Math.ceil(matches.length / pageSize));
  const requestedPage = Number(params.get('page') || 1);
  const page = Math.min(pages, Math.max(1, Number.isFinite(requestedPage) ? Math.floor(requestedPage) : 1));
  const selected = cases.find(r => r.id === params.get('case'));
  const selectedIndex = matches.findIndex(r => r.id === selected?.id);
  function update(values: Record<string, string | null>, replace = false) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(values)) { if (value && value !== 'all') next.set(key, value); else next.delete(key); }
    setParams(next, { replace });
  }
  function filter(key: string, value: string) { update({ [key]: value, page: null, case: null }, true); }
  function choose(r: RequestCase) {
    const index = matches.findIndex(item => item.id === r.id);
    update({ case: r.id, page: String(Math.floor(Math.max(0, index) / pageSize) + 1) });
    requestAnimationFrame(() => heading.current?.focus());
  }
  async function refresh() {
    setBusy(true); setError(false);
    try { await onRefresh?.(); setRevision(v => v + 1); } catch { setError(true); } finally { setBusy(false); }
  }
  return <div className={'admin-inbox claims-panel' + (selected ? ' has-selection' : '')}>
    <header className="inbox-heading"><div><span className="eyebrow">{t('inbox.eyebrow')}</span><h1>{t('claims.title')}</h1><p>{t('inbox.intro')}</p></div><button className="button secondary" disabled={busy} onClick={() => void refresh()}><RefreshCw size={16} className={busy ? 'spin' : ''}/>{t('caseAdmin.refresh')}</button></header>
    {error && <p className="error-text" role="alert">{t('trace.error')}</p>}
    <div className="inbox-overview" aria-label={t('inbox.overview')}>
      {[{ title: 'inbox.all', value: 'all', count: cases.length }, { title: 'claims.inReview', value: 'in_review', count: cases.filter(r => stage(r) === 'in_review').length }, { title: 'claims.pendingApproval', value: 'refund_pending', count: cases.filter(r => r.refund?.status === 'pending').length }, { title: 'inbox.refunded', value: 'refunded', count: cases.filter(r => stage(r) === 'refunded').length }].map(item => <button key={item.value} aria-pressed={status === item.value} onClick={() => filter('status', item.value)}><strong>{item.count}</strong><span>{t(item.title)}</span></button>)}
    </div>
    <div className="claims-filters inbox-filters"><label>{t('claims.searchLabel')}<span className="inbox-search"><Search size={17}/><input type="search" value={query} maxLength={100} placeholder={t('claims.search')} onChange={e => filter('q', e.target.value)}/></span></label><label>{t('customer')}<select value={user} onChange={e => filter('user', e.target.value)}><option value="">{t('auditAll')}</option>{users.filter(u => u.role === 'customer').map(u => <option key={u.id} value={u.id}>{u.name} · {u.email}</option>)}</select></label><label>{t('status')}<select value={status} onChange={e => filter('status', e.target.value)}>{['all', 'received', 'delivered', 'in_review', 'approved', 'refunded', 'handed_off', 'refund_pending', 'refund_approved', 'refund_rejected'].map(value => <option key={value} value={value}>{t(value.startsWith('refund_') ? 'refundStatus.' + value.slice(7) : value === 'all' || value === 'handed_off' ? value : 'claimStage.' + value)}</option>)}</select></label></div>
    <div className="claims-workspace inbox-workspace">
      <section className="claims-list inbox-list" aria-label={t('claims.list')}><div className="inbox-list-title"><h2>{t('inbox.queue')}</h2><span className="trace-count">{matches.length}</span></div>
        <div className="inbox-rows" ref={rows}>{matches.slice((page - 1) * pageSize, page * pageSize).map(r => <button className={'claim-choice ' + (selected?.id === r.id ? 'selected' : '')} key={r.id} aria-pressed={selected?.id === r.id} data-claim-id={r.id} onClick={() => choose(r)}><div><code>{r.id}</code><RequestStatus request={r}/></div><strong>{r.catalogServiceId ? serviceTitle(r.catalogServiceId, i18n.language as Locale) : t(r.reason === 'amount' ? 'amountReason' : r.reason)}</strong><span>{r.customerName}</span></button>)}{!matches.length && <div className="empty-panel"><FileSearch size={28}/><p>{t('noMatchingRequests')}</p><button className="text-link" onClick={() => update({ user: null, q: null, status: null, page: null, case: null })}>{t('inbox.clear')}</button></div>}</div>
        <nav className="inbox-pagination" aria-label={t('inbox.pagination')}><button className="icon-button" aria-label={t('inbox.previousPage')} disabled={page === 1} onClick={() => update({ page: String(page - 1) })}><ChevronLeft size={18}/></button><span role="status">{t('inbox.page', { page, pages })}</span><button className="icon-button" aria-label={t('inbox.nextPage')} disabled={page === pages} onClick={() => update({ page: String(page + 1) })}><ChevronRight size={18}/></button></nav>
      </section>
      <div className="claims-detail inbox-detail">{selected ? <><header className="claims-detail-header"><button className="button secondary inbox-back" aria-label={t("inbox.back")} title={t("inbox.back")} onClick={() => update({ case: null })}><ArrowLeft size={16}/><span>{t('inbox.back')}</span></button><div><span className="eyebrow">{selected.id}</span><h2 ref={heading} tabIndex={-1}>{selected.customerName}</h2></div><div className="inbox-case-nav"><button className="icon-button" aria-label={t('inbox.previousCase')} disabled={selectedIndex <= 0} onClick={() => choose(matches[selectedIndex - 1])}><ChevronLeft size={18}/></button><button className="icon-button" aria-label={t('inbox.nextCase')} disabled={selectedIndex < 0 || selectedIndex === matches.length - 1} onClick={() => choose(matches[selectedIndex + 1])}><ChevronRight size={18}/></button></div></header><ClaimTrace key={selected.id} request={selected} admin onChanged={onRefresh} refreshVersion={revision}/></> : <div className="claims-empty"><FileSearch size={38}/><h2>{t('claims.choose')}</h2><p>{t('inbox.chooseHint')}</p></div>}</div>
    </div>
  </div>;
}
