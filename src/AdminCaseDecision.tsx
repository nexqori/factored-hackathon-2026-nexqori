import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { RefundPanel } from './RefundPanel';
import type { RequestCase } from './types';

const stages = ['received', 'delivered', 'in_review', 'approved', 'refunded'] as const;
export function AdminCaseDecision({ request, onChanged }: {
  request: RequestCase; onChanged: () => Promise<unknown>;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false); const [note, setNote] = useState('');
  const current = request.refund?.creditTransactionId ? 'refunded' : request.handling?.stage || (request.status === 'in_review' ? 'in_review' : 'received');
  const index = stages.indexOf(current);
  const next = stages[index + 1];
  async function advance() {
    if (!confirmed || busy || !next || next === 'refunded') return;
    setBusy(true); setError('');
    try {
      await api('/admin/requests/' + encodeURIComponent(request.id) + '/stage', 'POST', { confirmed: true, stage: next, note: next === 'approved' ? note : '' });
      setConfirmed(false); setNote(''); await onChanged();
    } catch (error) { setError(error instanceof ApiError ? error.code : 'generic'); }
    finally { setBusy(false); }
  }
  return <section className="admin-case-decision trace-section" aria-label={t('caseDecision.title')}>
    <h3>{t('caseDecision.title')}</h3><p>{t('claimStage.hint')}</p>
    <ol className="claim-stage-list" aria-label={t('claimStage.progress')}>
      {stages.map((stage, position) => <li key={stage} aria-current={position === index ? 'step' : undefined} className={position <= index ? 'done' : ''}><span aria-hidden="true">{position <= index ? '✓' : position + 1}</span>{t('claimStage.' + stage)}</li>)}
    </ol>
    {request.handling?.note && <p className="case-details">{request.handling.note}</p>}
    {error && <p role="alert" className="error-text">{t('error.' + error, { defaultValue: t('error.generic') })}</p>}
    {next && next !== 'refunded' && !request.refund?.creditTransactionId && request.refund?.status !== 'rejected' && <div className="case-review-start form-stack">
      {next === 'approved' && <label>{t('claimStage.note')}<textarea aria-label={t('claimStage.note')} value={note} onChange={e => setNote(e.target.value)} minLength={10} maxLength={1000} disabled={busy} aria-describedby="claim-note-hint"/><small id="claim-note-hint" className="muted">{t('claimStage.noteHint', {count: note.trim().length})}</small></label>}
      <label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={event => setConfirmed(event.target.checked)}/>{t('claimStage.confirm.' + next)}</label>
      <button className="button primary" disabled={!confirmed || busy || (next === 'approved' && note.trim().length < 10)} onClick={() => void advance()}>{t(busy ? 'loading' : 'claimStage.action.' + next)}</button>
    </div>}
    <RefundPanel key={request.id + ':' + request.refund?.status + ':' + current} requestId={request.id} admin onBusy={setBusy} onChanged={onChanged}/>
    <p className="case-decision-scope">{t('claimStage.scope')}</p>
  </section>;
}
