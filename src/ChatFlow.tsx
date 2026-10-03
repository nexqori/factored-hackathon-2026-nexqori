import { useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { Dialog } from './components';
import { catalogIds, serviceTitle } from './catalog';
import type { Locale } from './i18n';
import type { Message } from './types';

export type FlowResult = { canDocument?: boolean; execution: {phase: string}; workflow_id: string; workflow_revision: number; state: string; reply: string;
  suggestedTransaction?: {id:string} | null;
  selectedRequestId?: string | null;
  jev: {intent?: string; status: string}; triage: {family?: string}; canRegister: boolean; requestId: string | null; latency_ms: number;
  missing_fields: string[]; verified_facts: {field: string; value: string; reference_id: string}[];
  trace: {node_id: string; label: Record<string,string>; kind: string; status: string; latency_ms: number}[] };

export type ClaimRegistration = { id: string; message: Message; summary: string; nextStep: string; flow: FlowResult };
type ClaimPreview = { summary: string; previewToken: string; intent: string; transactionId: string | null; operationLabel: string; nextStep: string };

export function ChatFlow({ result, conversationId, onRegistered, readOnly = false, technical = false }: { result: FlowResult; conversationId: string; text?: string; readOnly?: boolean; technical?: boolean; onRegistered: (claim: ClaimRegistration) => void }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const summaryLabelId = useId();
  const [review, setReview] = useState(false); const [details, setDetails] = useState(''); const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [preview, setPreview] = useState<ClaimPreview | null>(null);
  const attempt = useRef<{signature:string; key:string} | null>(null);
  async function loadPreview() {
    setReview(true); setBusy(true); setError(''); setConfirmed(false); setPreview(null);
    try {
      const value = await api<ClaimPreview>('/conversations/' + conversationId + '/claim-preview?locale=' + locale);
      setPreview(value); setDetails(value.summary); attempt.current = null;
    } catch(e) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
    finally { setBusy(false); }
  }
  async function register() {
    if (!confirmed || busy || !preview || details.trim().length < 10) return; setBusy(true); setError('');
    const body = {details:details.trim(), confirmed:true, locale, previewToken:preview.previewToken};
    const signature = JSON.stringify(body);
    if (attempt.current?.signature !== signature) attempt.current = {signature, key:crypto.randomUUID()};
    try { const value = await api<ClaimRegistration>('/conversations/' + conversationId + '/claim', 'POST', {...body, requestKey:attempt.current.key}); setReview(false); onRegistered(value); }
    catch(e) {
      if (e instanceof ApiError && e.code === 'claim_preview_outdated') { setPreview(null); setConfirmed(false); }
      setError('error.' + (e instanceof ApiError ? e.code : 'generic'));
    } finally { setBusy(false); }
  }
  return <section className="chat-flow" aria-label={t('chatFlow.title')}><h3>{t('chatFlow.title')}</h3>
    <div className="flow-result"><strong>{result.jev.intent && catalogIds.has(result.jev.intent) ? serviceTitle(result.jev.intent, locale) : t(i18n.exists('chatFlow.intent.' + result.jev.intent) ? 'chatFlow.intent.' + result.jev.intent : 'chatFlow.classifying')}</strong><p>{t('chatFlow.state.' + result.state)}</p></div>
    {!!result.verified_facts.length && <details><summary>{t('chatFlow.evidence', {count: result.verified_facts.length})}</summary><ul className="chat-flow-facts">{result.verified_facts.map(f => <li key={f.field}>{f.value}{technical && <small>· {f.reference_id}</small>}</li>)}</ul></details>}
    {technical && <details><summary>{t('chatFlow.steps', {count: result.trace.length})} · {(result.latency_ms / 1000).toFixed(1)} s</summary><ol>{result.trace.map((step, index) => <li key={index}>{step.label[locale]}<small>{t(step.status === 'ok' ? 'chatFlow.checked' : 'chatFlow.failed')} · {step.latency_ms.toFixed(0)} ms</small></li>)}</ol><details><summary>{t('chatFlow.json')}</summary><pre>{JSON.stringify(result,null,2)}</pre></details></details>}
    {!readOnly && result.canRegister && <button className="button primary wide" onClick={() => { void loadPreview(); }}>{t('chatFlow.prepareClaim')}</button>}
    {!readOnly && result.requestId && <Link className="button secondary wide" to={'/complaints?case=' + encodeURIComponent(result.requestId)}>{t('chatFlow.follow')} · {result.requestId}</Link>}
    {!readOnly && result.jev.intent === 'unrecognized-charge' && <p><Link to="/cards">{t('chatFlow.cards')}</Link></p>}
    {review && <Dialog title={t('chatFlow.prepareClaim')} onClose={() => setReview(false)} busy={busy} className="chat-claim-review"><form className="form-stack" onSubmit={e => { e.preventDefault(); void register(); }}>
      <p>{t('chatClaim.reviewHint')}</p>
      {busy && !preview && <p role="status">{t('loading')}</p>}
      {preview && <>
        {preview.operationLabel && <p className="chat-claim-operation">{preview.operationLabel}</p>}
        <label><span id={summaryLabelId}>{t('chatClaim.summary')}</span><textarea aria-labelledby={summaryLabelId} required minLength={10} maxLength={1000} rows={6} value={details} disabled={busy} onChange={e => { setDetails(e.target.value); setConfirmed(false); }}/></label>
        <p className="muted">{t('chatClaim.nextStep')} {preview.nextStep}</p>
        <label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)}/>{t('chatClaim.confirm')}</label>
      </>}
      {error && <p className="error-text" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}
      {!preview && !busy && <button type="button" className="button secondary" onClick={() => { void loadPreview(); }}>{t('chatClaim.reload')}</button>}
      <button className="button primary" disabled={!confirmed || busy || !preview || details.trim().length < 10}>{t(busy ? 'loading' : 'chatClaim.register')}</button>
    </form></Dialog>}
  </section>;
}
