import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { RefundPanel } from './RefundPanel';
import type { RequestCase } from './types';

/** Operates on the authenticated server case; evidence never authorizes a decision. */
export function AdminCaseDecision({ request, canStartReview, onChanged }: {
  request: RequestCase; canStartReview: boolean; onChanged: () => Promise<unknown>;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  async function review() {
    if (!confirmed || busy) return;
    setBusy(true); setError('');
    try { await api('/admin/requests/' + encodeURIComponent(request.id) + '/review', 'POST', { confirmed: true }); await onChanged(); }
    catch (error) { setError(error instanceof ApiError ? error.code : 'generic'); }
    finally { setBusy(false); }
  }
  return <section className="admin-case-decision trace-section" aria-label={t('caseDecision.title')}>
    <h3>{t('caseDecision.title')}</h3><p>{t('caseDecision.hint')}</p>
    {error && <p role="alert" className="error-text">{t('error.' + error, { defaultValue: t('error.generic') })}</p>}
    {canStartReview && <div className="case-review-start form-stack"><label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)}/>{t('caseDecision.reviewConfirm')}</label><button className="button secondary" disabled={!confirmed || busy} onClick={() => void review()}>{t(busy ? 'loading' : 'caseDecision.start')}</button></div>}
    <RefundPanel key={request.id + ':' + request.refund?.status} requestId={request.id} admin onBusy={setBusy} onChanged={onChanged}/>
    <p className="case-decision-scope">{t('caseDecision.scope')}</p>
  </section>;
}
