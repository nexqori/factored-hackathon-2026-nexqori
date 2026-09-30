import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { formatMoney } from './components';
import type { Locale } from './i18n';

type Refund = { id: string; requestId: string; transactionId: string; amountMinor: number; destinationLast4: string; status: 'pending' | 'approved' | 'rejected'; decisionNote: string | null; creditTransactionId: string | null };
type State = { eligible: boolean; refund: Refund | null; reason: string | null; preview: { amountMinor: number; destinationLast4: string; merchant: string; transactionId: string } | null };

export function RefundPanel({ requestId, admin, onChanged, onBusy }: { requestId: string; admin: boolean; onChanged: () => Promise<unknown>; onBusy: (value: boolean) => void }) {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<State | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false); const [password, setPassword] = useState(''); const [note, setNote] = useState('');
  const [decision, setDecision] = useState('approve'); const [key] = useState(() => crypto.randomUUID());
  const path = (admin ? '/admin' : '') + '/requests/' + encodeURIComponent(requestId) + '/refund';
  useEffect(() => { const control = new AbortController(); void api<State>(path, 'GET', undefined, control.signal).then(setState).catch(() => { if (!control.signal.aborted) setError(t('error.generic')); }); return () => control.abort(); }, [path]);
  async function submit(e: FormEvent) {
    e.preventDefault(); if (!confirm || busy) return; setBusy(true); onBusy(true); setError(''); const submitted = password; setPassword('');
    try {
      const refund = await api<Refund>(admin ? '/admin/refunds/' + state!.refund!.id + '/decision' : path, 'POST', admin ? { confirmed: true, requestKey: key, decision, note, password: submitted } : { confirmed: true, requestKey: key });
      setState({ eligible: false, refund, reason: null, preview: null }); setConfirm(false);
      await onChanged();
    } catch (e) { const k = e instanceof ApiError ? 'error.' + e.code : 'error.generic'; setError(t(i18n.exists(k) ? k : 'error.generic')); }
    finally { setBusy(false); onBusy(false); }
  }
  const amount = state?.refund || state?.preview;
  const canAct = !!state && (admin ? state.refund?.status === 'pending' : state.eligible);
  return <section className="refund-panel" aria-label={t('refundTitle')}><h3>{t('refundTitle')}</h3>{!state && !error && <p role="status">{t('loading')}</p>}{error && <p role="alert" className="error-text">{error}</p>}
    {amount && <dl className="refund-summary"><div><dt>{t('amount')}</dt><dd>{formatMoney(amount.amountMinor, i18n.language as Locale)}</dd></div><div><dt>{t('refundDestination')}</dt><dd>•••• {amount.destinationLast4}</dd></div><div><dt>{t('reference')}</dt><dd>{amount.transactionId}</dd></div></dl>}
    {state?.refund && <div role="status"><p><strong>{t('refundStatus.' + state.refund.status)}</strong></p>{state.refund.decisionNote && <p className="case-details">{state.refund.decisionNote}</p>}{state.refund.creditTransactionId && <p>{t('refundCreditReference')}: {state.refund.creditTransactionId}</p>}</div>}
    {state && !state.refund && !canAct && <p className="muted">{t(admin && state.eligible ? 'refundNotRequested' : 'error.' + state.reason)}</p>}
    {canAct && <form onSubmit={submit} className="form-stack"><p>{t(admin ? 'refundReviewExplain' : 'refundExplain')}</p>{admin && <><label>{t('refundDecision')}<select disabled={busy} value={decision} onChange={e => { setDecision(e.target.value); setConfirm(false); }}><option value="approve">{t('refundApprove')}</option><option value="reject">{t('refundReject')}</option></select></label><label>{t('refundEvidence')}<textarea required minLength={10} maxLength={1000} disabled={busy} value={note} onChange={e => setNote(e.target.value)} /></label><label>{t('password')}<input type="password" autoComplete="current-password" required maxLength={256} disabled={busy} value={password} onChange={e => setPassword(e.target.value)} /></label></>}
    <label className="checkbox-label"><input type="checkbox" required disabled={busy} checked={confirm} onChange={e => setConfirm(e.target.checked)}/>{t(admin ? decision === 'approve' ? 'refundConfirmApprove' : 'refundConfirmReject' : 'refundConfirmRequest')}</label><button className="button primary" disabled={busy || !confirm}>{t(busy ? 'loading' : admin ? 'refundSaveDecision' : 'refundRequest')}</button></form>}
  </section>;
}
