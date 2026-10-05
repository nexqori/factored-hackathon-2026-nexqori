import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowUpRight, FileSearch } from 'lucide-react';
import { AdminClaimsPanel } from './AdminClaimsPanel';
import { ClaimTrace } from './ClaimTrace';
import { RequestStatus } from './RequestProgress';
import { serviceTitle } from './catalog';
import type { Locale } from './i18n';
import type { RequestCase, User } from './types';

export function ClaimsPanel({ users, requests, onRequest, admin = true, onCreate, onRefresh }: { users: User[]; requests: RequestCase[]; onRequest: (id: string) => void; admin?: boolean; onCreate?: () => void; onRefresh?: () => Promise<unknown> }) {
  const { t, i18n } = useTranslation(); const [params, setParams] = useSearchParams();
  const userId = params.get('user') || ''; const caseId = params.get('case') || '';
  const [search, setSearch] = useState(''); const [status, setStatus] = useState('all'); const [limit, setLimit] = useState(30);
  const [refreshing, setRefreshing] = useState(false); const [refreshError, setRefreshError] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const detail = useRef<HTMLDivElement>(null);
  const focusedCase = useRef('');
  useEffect(() => {
    if (!admin && caseId && requests.some(r => r.id === caseId && r.kind === 'claim') && focusedCase.current !== caseId) {
      // Wait for the submitted draft dialog to release its scroll lock.
      let second = 0;
      const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => {
        focusedCase.current = caseId;
        detail.current?.focus({ preventScroll: true });
        detail.current?.scrollIntoView({ block: 'start', behavior: 'instant' });
      }); });
      return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
    }
  }, [admin, caseId, requests]);
  const owned = requests.filter(r => r.kind === 'claim' && (!userId || r.userId === userId));
  const selected = owned.find(r => r.id === caseId);
  const visible = owned.filter(r => (status === 'all' || (status.startsWith('refund_') ? r.refund?.status === status.slice(7) : r.status === status)) && [r.id, r.customerName, r.details, r.refund?.id, r.transactionId, r.refund?.creditTransactionId].some(s => s?.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())));
  if (admin) return <AdminClaimsPanel users={users} requests={requests} onRefresh={onRefresh}/>;
  return <div className="claims-panel"><div className="page-heading"><p className="eyebrow">{admin ? t('users') + ' / ' : ''}{t('trace.title')}</p><h1>{t(admin ? 'claims.title' : 'myClaims')}</h1><p>{t(admin ? 'claims.intro' : 'claims.customerIntro')}</p></div>
    {onRefresh && <div className="claims-refresh"><button className="button secondary" disabled={refreshing} onClick={async () => { setRefreshing(true); setRefreshError(false); try { await onRefresh(); setRefreshVersion(value => value + 1); } catch { setRefreshError(true); } finally { setRefreshing(false); } }}>{t(refreshing ? 'loading' : 'caseAdmin.refresh')}</button>{refreshError && <p role="alert">{t('trace.error')}</p>}</div>}
    <>{!admin && <button className="button primary customer-claims-intro" onClick={onCreate}>{t("newClaim")}</button>}</><div className="claims-filters">{admin && <label>{t('customer')}<select value={userId} onChange={e => { setParams(e.target.value ? { user: e.target.value } : {}); setSearch(''); setStatus('all'); setLimit(30); }}><option value="">{t('auditAll')}</option>{users.filter(u => u.role === 'customer').map(u => <option key={u.id} value={u.id}>{u.name} · {u.email}</option>)}</select></label>}<label>{t('claims.searchLabel')}<input type="search" maxLength={100} value={search} placeholder={t('claims.search')} onChange={e => { setSearch(e.target.value); setLimit(30); }} /></label><label>{t('status')}<select value={status} onChange={e => { setStatus(e.target.value); setLimit(30); }}>{['all', 'received', 'in_review', 'handed_off', 'refund_pending', 'refund_approved', 'refund_rejected'].map(s => <option key={s} value={s}>{t(s.startsWith('refund_') ? 'refundStatus.' + s.slice(7) : s)}</option>)}</select></label></div>
    <div className="claims-metrics">{[{ key: 'claims.total', count: owned.length }, { key: 'claims.pendingApproval', count: owned.filter(r => r.refund?.status === 'pending').length }, { key: 'claims.inReview', count: owned.filter(r => r.status === 'in_review').length }, { key: 'claims.handedOff', count: owned.filter(r => r.status === 'handed_off').length }].map(m => <div key={m.key}><strong>{m.count}</strong><span>{t(m.key)}</span></div>)}</div>
    <div className="claims-workspace"><section className="claims-list" aria-label={t('claims.list')}><div className="trace-toolbar"><h2>{t('claims.list')}</h2><span>{visible.length}</span></div>{visible.slice(0, limit).map(r => <button className={'claim-choice ' + (selected?.id === r.id ? 'selected' : '')} key={r.id} aria-pressed={selected?.id === r.id} data-claim-id={r.id} onClick={() => setParams({ user: r.userId, case: r.id })}><div><code>{r.id}</code><RequestStatus request={r} /></div><strong>{r.catalogServiceId ? serviceTitle(r.catalogServiceId, i18n.language as Locale) : t(r.reason === 'amount' ? 'amountReason' : r.reason)}</strong><span>{r.customerName}</span><p>{r.details}</p></button>)}{!visible.length && <p className="empty-panel">{t('noMatchingRequests')}</p>}{visible.length > limit && <button className="button secondary" onClick={() => setLimit(limit + 30)}>{t('loadMore')}</button>}</section>
      <div className="claims-detail" ref={detail} tabIndex={-1}>{selected ? <><div className="claims-detail-header"><span>{selected.customerName}</span>{!admin && <button className="button primary" onClick={() => onRequest(selected.id)}>{t('claims.manage')}<ArrowUpRight size={16} /></button>}</div><ClaimTrace key={selected.id} request={selected} admin={admin} onChanged={onRefresh} refreshVersion={refreshVersion} /></> : <div className="claims-empty"><FileSearch size={38} /><h2>{t('claims.choose')}</h2><p>{t('claims.chooseHint')}</p></div>}</div>
    </div>
  </div>;
}
