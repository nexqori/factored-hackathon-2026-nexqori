import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';

type Ticket = {
  id: string; customerName: string; status: string; assignedTo: string | null;
  context: { intent: string | null; reason: string; language: string; last_evidence?: string | null; user_supplied_fields?: Record<string, string | boolean>; messages: {role: string; text: string; language: string; timestamp: string}[] };
  messages: {id: string; role: string; text: string; name: string; at: string}[];
};

export function HumanSupport({ operator = false, signal = 0 }: {operator?: boolean; signal?: number}) {
  const { t } = useTranslation();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const base = operator ? '/admin/chat-handoffs' : '/assistant/handoffs';
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try { const next = await api<Ticket[]>(base); if (active) { setTickets(next); setError(''); } }
      catch (e) { if (active) setError(e instanceof ApiError ? e.code : 'generic'); }
      finally { if (active) timer = setTimeout(refresh, 5000); }
    }
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [base, signal]);
  async function act(ticket: Ticket, confirm: boolean) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const next = await api<Ticket>(base + '/' + ticket.id + (confirm ? '/confirm' : '/messages'), 'POST',
        confirm ? {confirmed: true} : {text: drafts[ticket.id], messageId: crypto.randomUUID()});
      setTickets(previous => previous.map(item => item.id === next.id ? next : item));
      if (!confirm) setDrafts(previous => ({...previous, [ticket.id]: ''}));
    } catch (e) { setError(e instanceof ApiError ? e.code : 'generic'); }
    finally { setBusy(false); }
  }
  if (!operator && !tickets.length && !error) return null;
  return <section className="human-support panel" aria-label={t('humanInbox')}>
    <h2>{t('humanInbox')}</h2><p className="muted">{t('humanTemporary')}</p>
    {error && <p role="alert" className="error-text">{t('error.' + error, {defaultValue: t('error.generic')})}</p>}
    {!tickets.length && <p>{t('humanEmpty')}</p>}
    {tickets.map(ticket => <details key={ticket.id} className="human-ticket" open={ticket.status === 'draft' ? true : undefined}>
      <summary>{operator ? ticket.customerName : t('humanThread')} · {t('humanStatus.' + ticket.status)}</summary>
      <p className="muted">{t('reference')}: {ticket.id}</p>
      <details><summary>{t('humanContext')}</summary><div className="human-transcript" tabIndex={0} role="region" aria-label={t('humanContext')}>
        <p>{t('humanReason')}: {t('humanReason.' + ticket.context.reason, {defaultValue: ticket.context.reason})}</p>
        {operator && <><p>{t('humanIntent')}: {ticket.context.intent || '-'}</p>
          <p>{t('humanEvidence')}: {ticket.context.last_evidence || '-'}</p>
          {!!Object.keys(ticket.context.user_supplied_fields || {}).length && <><p>{t('humanFields')}</p>
            <dl>{Object.entries(ticket.context.user_supplied_fields || {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl></>}
        </>}
        {ticket.context.messages.map((m, index) => <p key={index} lang={m.language}><strong>{t(m.role === 'user' ? 'customer' : 'assistant')}: </strong>{m.text}</p>)}
      </div></details>
      {ticket.status === 'draft' ? <><p>{t('humanConsent')}</p><button className="button secondary" disabled={busy} onClick={() => { void act(ticket, true); }}>{t('humanConfirm')}</button></> : <>
        <div className="human-transcript" tabIndex={0} role="log" aria-live="polite" aria-label={t('humanMessages')}>
          {ticket.messages.map(m => <p key={m.id}><strong>{m.name}: </strong>{m.text}</p>)}
        </div>
        <form className="form-stack" onSubmit={event => { event.preventDefault(); void act(ticket, false); }}>
          <label>{t('humanReply')}<textarea maxLength={2000} value={drafts[ticket.id] || ''} onChange={e => setDrafts(previous => ({...previous, [ticket.id]: e.target.value}))} disabled={busy} /></label>
          <button className="button secondary" disabled={busy || !drafts[ticket.id]?.trim()}>{t('send')}</button>
        </form>
      </>}
    </details>)}
  </section>;
}
