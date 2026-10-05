import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from './components';
import type { RequestCase } from './types';
import './request-progress.css';

export function RequestStatus({ request }: { request: RequestCase }) {
  const { t } = useTranslation();
  if (request.handling?.updatedAt && request.status !== 'handed_off' && !request.refund?.creditTransactionId && request.refund?.status !== 'rejected') return <span className="badge request-progress status-in_review"><span aria-hidden="true" />{t('claimStage.' + request.handling.stage)}</span>;
  if (!request.refund) return <Badge status={request.status} />;
  const status = request.refund.status;
  return <span className={'badge request-progress status-' + ({pending:'in_review',approved:'completed',rejected:'declined'}[status])}><span aria-hidden="true" />{t('refundStatus.' + status)}</span>;
}

export function RequestOperationReference({ request }: { request: RequestCase }) {
  const { t } = useTranslation();
  return request.refund ? <p className="operation-reference"><span>{t('operationId')}</span><code>{request.refund.id}</code></p> : null;
}

export function RequestCollection({ requests, renderCase }: { requests: RequestCase[]; renderCase: (request: RequestCase) => ReactNode }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [status,setStatus] = useState('');
  const search = query.trim().toLocaleLowerCase();
  const filtered = requests.filter(r => (!status || r.status===status) && [r.id, r.refund?.id, r.refund?.creditTransactionId, r.customerName].some(value => value?.toLocaleLowerCase().includes(search)));
  return <><div className="request-filters"><label className="request-search">{t('searchRequests')}<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t('searchRequestsPlaceholder')} maxLength={100} /></label><label className="request-search">{t("status")}<select value={status} onChange={e=>setStatus(e.target.value)}><option value="">{t("allStatuses")}</option>{["received","in_review","handed_off"].map(v=><option key={v} value={v}>{t(v)}</option>)}</select></label></div>
    <div className="requests-grid">{filtered.map(renderCase)}</div>{(query || status) && !filtered.length && <p role="status" className="muted">{t('noMatchingRequests')}</p>}</>;
}
