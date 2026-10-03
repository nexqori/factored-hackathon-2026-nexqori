import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { Dialog } from './components';
import { catalogIds, serviceTitle } from './catalog';
import type { Locale } from './i18n';

export type FlowResult = { execution: {phase: string}; workflow_id: string; workflow_revision: number; state: string; reply: string;
  jev: {intent?: string; status: string}; triage: {family?: string}; canRegister: boolean; requestId: string | null; latency_ms: number;
  missing_fields: string[]; verified_facts: {field: string; value: string; reference_id: string}[];
  trace: {node_id: string; label: Record<string,string>; kind: string; status: string; latency_ms: number}[] };

export function ChatFlow({ result, conversationId, text, onRegistered, readOnly = false, technical = false }: { result: FlowResult; conversationId: string; text: string; readOnly?: boolean; technical?: boolean; onRegistered: (id: string) => void }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [review, setReview] = useState(false); const [details, setDetails] = useState(''); const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [requestKey] = useState(() => crypto.randomUUID());
  async function register() {
    if (!confirmed || busy) return; setBusy(true); setError('');
    try { const value = await api<{id: string}>('/conversations/' + conversationId + '/claim', 'POST', { details, confirmed:true, requestKey }); setReview(false); onRegistered(value.id); }
    catch(e) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); } finally { setBusy(false); }
  }
  return <section className="chat-flow" aria-label={t('chatFlow.title')}><h3>{t('chatFlow.title')}</h3>
    <div className="flow-result"><strong>{result.jev.intent && catalogIds.has(result.jev.intent) ? serviceTitle(result.jev.intent, locale) : t(i18n.exists('chatFlow.intent.' + result.jev.intent) ? 'chatFlow.intent.' + result.jev.intent : 'chatFlow.classifying')}</strong><p>{t('chatFlow.state.' + result.state)}</p></div>
    {!!result.verified_facts.length && <details><summary>{t('chatFlow.evidence', {count: result.verified_facts.length})}</summary><ul className="chat-flow-facts">{result.verified_facts.map(f => <li key={f.field}>{f.value}{technical && <small>· {f.reference_id}</small>}</li>)}</ul></details>}
    {technical && <details><summary>{t('chatFlow.steps', {count: result.trace.length})} · {(result.latency_ms / 1000).toFixed(1)} s</summary><ol>{result.trace.map((step, index) => <li key={index}>{step.label[locale]}<small>{t(step.status === 'ok' ? 'chatFlow.checked' : 'chatFlow.failed')} · {step.latency_ms.toFixed(0)} ms</small></li>)}</ol><details><summary>{t('chatFlow.json')}</summary><pre>{JSON.stringify(result,null,2)}</pre></details></details>}
    {!readOnly && result.canRegister && <button className="button primary wide" onClick={() => { setDetails(text.slice(0,1000)); setReview(true); setConfirmed(false); }}>{t('chatFlow.prepareClaim')}</button>}
    {!readOnly && result.requestId && <Link className="button secondary wide" to={'/complaints?case=' + encodeURIComponent(result.requestId)}>{t('chatFlow.follow')} · {result.requestId}</Link>}
    {!readOnly && result.jev.intent === 'unrecognized-charge' && <p><Link to="/cards">{t('chatFlow.cards')}</Link></p>}
    {review && <Dialog title={t('chatFlow.prepareClaim')} onClose={() => setReview(false)} busy={busy}><form className="form-stack" onSubmit={e => { e.preventDefault(); void register(); }}><p>{t('chatFlow.confirmHint')}</p><label>{t('detailLabel')}<textarea required minLength={10} maxLength={1000} rows={5} value={details} onChange={e => setDetails(e.target.value)}/></label><label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>{t('confirmCheck')}</label>{error && <p role="alert">{t(error)}</p>}<button className="button primary" disabled={!confirmed || busy}>{t(busy ? 'loading' : 'confirm')}</button></form></Dialog>}
  </section>;
}
