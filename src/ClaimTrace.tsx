import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Clock3, FileText, MessageCircle, RefreshCw } from 'lucide-react';
import { api } from './api';
import { Badge, formatMoney } from './components';
import { ChatFlow } from './ChatFlow';
import { RequestStatus } from './RequestProgress';
import type { Locale } from './i18n';
import type { AuditEvent, Conversation, ConversationPage, RequestCase } from './types';
import './claim-trace.css';

type Relation = 'request' | 'transaction' | 'conversation' | 'product';
type Trace = {
  request: RequestCase; customer: { id: string; name: string }; observedAt: string; outcome: string;
  transaction: { id: string; productId: string; merchant: string; amountMinor: number; currency: string; status: string; date: string } | null;
  product: { id: string; type: string; last4: string; status: string | null } | null;
  refund: { id: string; status: string; amountMinor: number; currency: string; destinationLast4: string; decisionNote: string | null; decidedAt: string | null; decidedBy: { id: string; name: string } | null; creditTransactionId: string | null } | null;
  events: (AuditEvent & { relation: Relation })[]; before: string | null; eventCount: number;
  conversations: (Conversation & { messageCount: number; relation: Relation })[]; conversationCount: number; nextConversationOffset: number | null;
};

export function ClaimTrace({ request, admin = false, compact = false }: { request: RequestCase; admin?: boolean; compact?: boolean }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [trace, setTrace] = useState<Trace | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const [tab, setTab] = useState<'detail' | 'json'>('detail');
  const [conversation, setConversation] = useState<ConversationPage | null>(null); const [conversationBusy, setConversationBusy] = useState(false); const [conversationError, setConversationError] = useState(false);
  const controller = useRef<AbortController | null>(null); const messageController = useRef<AbortController | null>(null);
  const path = admin ? `/admin/users/${encodeURIComponent(request.userId)}/requests/${encodeURIComponent(request.id)}/trace` : `/requests/${encodeURIComponent(request.id)}/trace`;
  const timestamp = (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value));
  async function load(mode: 'replace' | 'events' | 'conversations' = 'replace') {
    controller.current?.abort(); const control = new AbortController(); controller.current = control;
    setBusy(true); setError(false);
    const query = new URLSearchParams();
    if (mode === 'events' && trace?.before) query.set('before', trace.before);
    if (mode === 'conversations') query.set('conversationOffset', String(trace?.nextConversationOffset ?? 0));
    try {
      const value = await api<Trace>(path + '?' + query, 'GET', undefined, control.signal);
      setTrace(old => !old || mode === 'replace' ? value : mode === 'events'
        ? { ...old, events: [...old.events, ...value.events], before: value.before, eventCount: value.eventCount }
        : { ...old, conversations: [...old.conversations, ...value.conversations], nextConversationOffset: value.nextConversationOffset });
    } catch { if (!control.signal.aborted) setError(true); }
    finally { if (!control.signal.aborted) setBusy(false); }
  }
  useEffect(() => { setTrace(null); setConversation(null); void load(); return () => { controller.current?.abort(); messageController.current?.abort(); }; }, [path, request.updatedAt, request.refund?.status]);
  async function viewConversation(id: string, before?: string) {
    messageController.current?.abort(); const control = new AbortController(); messageController.current = control;
    setConversationBusy(true); setConversationError(false); if (!before) setConversation(null);
    try {
      const value = await api<ConversationPage>((admin ? '/admin' : '') + '/conversations/' + encodeURIComponent(id) + (before ? '?before=' + encodeURIComponent(before) : ''), 'GET', undefined, control.signal);
      setConversation(old => ({ ...value, messages: before && old ? [...value.messages, ...old.messages] : value.messages }));
    } catch { if (!control.signal.aborted) setConversationError(true); }
    finally { if (!control.signal.aborted) setConversationBusy(false); }
  }
  const eventTitle = (action: string) => action.startsWith('navigate_') ? t('navigationRecorded', { screen: t(action.slice(9)) }) : t('auditActions.' + action, { defaultValue: t('trace.recordedActivity') });
  function eventDescription(action: string) {
    const key = action.startsWith('navigate_') ? 'navigation' : action;
    return t('trace.event.' + key, { defaultValue: t('trace.event.other') });
  }
  return <section className={'claim-trace ' + (compact ? 'compact' : '')} aria-label={t('trace.title')} data-trace-ready={!!trace && !busy}>
    <div className="trace-toolbar"><h2>{t('trace.title')}</h2><button className="button secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={15} />{t('auditRefresh')}</button></div>
    <div className="trace-tabs" role="group" aria-label={t('trace.view')}><button aria-pressed={tab === 'detail'} onClick={() => setTab('detail')}>{t('trace.simple')}</button><button aria-pressed={tab === 'json'} onClick={() => setTab('json')}>{t('trace.json')}</button></div>
    {busy && <p role="status">{t('loading')}</p>}{error && <p role="alert" className="error-text">{t('trace.error')}</p>}
    {trace && (tab === 'json' ? <pre className="trace-json" tabIndex={0} aria-label={t('trace.json')}>{JSON.stringify(trace, null, 2)}</pre> : <>
      <div className="trace-current"><div><span className="eyebrow">{t('trace.now')}</span><h3>{t('trace.outcome.' + trace.outcome)}</h3><p>{t('trace.next.' + trace.outcome)}</p></div>{!compact && <RequestStatus request={trace.request} />}</div>
      <dl className="trace-facts"><div><dt>{t('reference')}</dt><dd><code>{request.id}</code></dd></div><div><dt>{t('customer')}</dt><dd>{trace.customer.name}</dd></div><div><dt>{t('trace.receivedAt')}</dt><dd>{timestamp(trace.request.createdAt)}</dd></div><div><dt>{t('trace.updatedAt')}</dt><dd>{timestamp(trace.request.updatedAt)}</dd></div></dl>
      {!compact && <section className="trace-section"><h3><FileText size={18} />{t('trace.report')}</h3><p className="trace-text">{trace.request.details}</p></section>}
      <section className="trace-section"><h3>{t('trace.evidence')}</h3><p className="muted">{t('trace.evidenceHint')}</p>{trace.transaction ? <dl className="trace-facts">
        <div><dt>{t('linkedMovement')}</dt><dd><code>{trace.transaction.id}</code></dd></div><div><dt>{t('trace.merchant')}</dt><dd>{trace.transaction.merchant}</dd></div>
        <div><dt>{t('amount')}</dt><dd>{formatMoney(trace.transaction.amountMinor, locale, trace.transaction.currency)}</dd></div><div><dt>{t('status')}</dt><dd><Badge status={trace.transaction.status} /></dd></div>
        <div><dt>{t('date')}</dt><dd>{timestamp(trace.transaction.date)}</dd></div>{trace.product && <div><dt>{t('product')}</dt><dd>{t(trace.product.type)} · •••• {trace.product.last4}{trace.product.status && <span> · {t(trace.product.status)}</span>}</dd></div>}
      </dl> : <p>{t('trace.noMovement')}</p>}</section>
      {!compact && trace.refund && <section className="trace-section"><h3>{t('trace.decision')}</h3><dl className="trace-facts"><div><dt>{t('operationId')}</dt><dd><code>{trace.refund.id}</code></dd></div><div><dt>{t('status')}</dt><dd>{t('refundStatus.' + trace.refund.status)}</dd></div><div><dt>{t('amount')}</dt><dd>{formatMoney(trace.refund.amountMinor, locale, trace.refund.currency)}</dd></div><div><dt>{t('refundDestination')}</dt><dd>•••• {trace.refund.destinationLast4}</dd></div>
        {trace.refund.decidedBy && <div><dt>{t('auditActor')}</dt><dd>{trace.refund.decidedBy.name}</dd></div>}{trace.refund.decidedAt && <div><dt>{t('date')}</dt><dd>{timestamp(trace.refund.decidedAt)}</dd></div>}{trace.refund.creditTransactionId && <div><dt>{t('refundCreditReference')}</dt><dd><code>{trace.refund.creditTransactionId}</code></dd></div>}</dl>
        {trace.refund.decisionNote && <div className="trace-decision"><strong>{t('refundEvidence')}</strong><p className="trace-text">{trace.refund.decisionNote}</p></div>}<p className="muted">{t('trace.separateStatus', { status: t(trace.request.status) })}</p></section>}
      <section className="trace-section"><h3><MessageCircle size={18} />{t('trace.conversations')} <span className="trace-count">{trace.conversationCount}</span></h3><p className="muted">{t('trace.conversationHint')}</p>
        {!trace.conversations.length && <p>{t(admin ? 'trace.noConversations' : 'trace.noOwnConversations')}</p>}<div className="trace-conversations">{trace.conversations.map(c => <button className="trace-conversation" key={c.id} disabled={conversationBusy} onClick={() => void viewConversation(c.id)} aria-label={t('trace.openConversation', { title: c.title || t('previousConversation') })}><strong>{c.title || t('previousConversation')}</strong><span>{timestamp(c.updatedAt)} · {t('trace.messageCount', { count: c.messageCount })}</span><small>{t('trace.relation.' + c.relation)} · {c.locale.toUpperCase()}</small></button>)}</div>
        {trace.nextConversationOffset !== null && <button className="text-link" disabled={busy} onClick={() => void load('conversations')}>{t('loadMore')}</button>}
        {conversationBusy && <p role="status">{t('loading')}</p>}{conversationError && <p role="alert" className="error-text">{t('trace.error')}</p>}
        {conversation && <section className="trace-transcript" aria-label={t('conversation')}><div className="trace-toolbar"><strong>{t('conversation')}</strong><button className="text-link" onClick={() => { messageController.current?.abort(); setConversationBusy(false); setConversation(null); }}>{t('close')}</button></div><p className="muted">{t('trace.originalLanguage')}</p>
          {conversation.before && <button className="text-link" disabled={conversationBusy} onClick={() => void viewConversation(conversation.conversation.id, conversation.before!)}>{t('olderMessages')}</button>}
          {conversation.flow && <ChatFlow readOnly result={conversation.flow} conversationId={conversation.conversation.id} text="" onRegistered={() => {}}/>}{conversation.messages.map(m => <article className={'trace-message ' + m.role} key={m.id}><strong>{t(m.role === 'user' ? 'customer' : 'assistant')}</strong><time dateTime={m.at}>{timestamp(m.at)}</time><p className="trace-text" lang={m.locale}>{m.text}</p></article>)}</section>}
      </section>
      <section className="trace-section"><h3><Clock3 size={18} />{t('trace.activity')} <span className="trace-count">{trace.eventCount}</span></h3><p className="muted">{t('trace.activityHint')}</p>
        <ol className="trace-events">{trace.events.map(e => <li key={e.id}><span className="trace-event-icon"><Check size={14} /></span><article><div className="trace-event-heading"><strong>{eventTitle(e.action)}</strong><time dateTime={e.at}>{timestamp(e.at)}</time></div><p>{eventDescription(e.action)}</p><div className="trace-event-meta"><span>{t('auditActor')}: {e.actorName}</span><span>{t('trace.relation.' + e.relation)}</span></div><details><summary>{t('trace.references')}</summary><dl><div><dt>{t('trace.auditId')}</dt><dd><code>{e.id}</code></dd></div>{e.transactionId && <div><dt>{t('linkedMovement')}</dt><dd><code>{e.transactionId}</code></dd></div>}{e.conversationId && <div><dt>{t('conversation')}</dt><dd><code>{e.conversationId}</code></dd></div>}<div><dt>{t('trace.eventCode')}</dt><dd><code>{e.action}</code></dd></div></dl></details></article></li>)}</ol>
        {!trace.events.length && <p>{t('trace.noEvents')}</p>}{trace.before && <button className="button secondary" disabled={busy} onClick={() => void load('events')}>{t('trace.olderEvents')}</button>}
      </section><p className="trace-source">{t('trace.observed', { date: timestamp(trace.observedAt) })}</p>
    </>)}
  </section>;
}
