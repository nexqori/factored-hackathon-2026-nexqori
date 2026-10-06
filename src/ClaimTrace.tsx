import { productLabelKey } from './productLabels';
import type { CardKind } from './types';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Check, Clock3, FileText, MessageCircle, RefreshCw } from 'lucide-react';
import { api } from './api';
import { Badge, formatMoney } from './components';
import { ChatFlow } from './ChatFlow';
import { AdminCaseDocuments } from './AdminCaseDocuments';
import { AttentionReview } from './AttentionReview';
import { AdminCaseDecision } from './AdminCaseDecision';
import { RequestStatus } from './RequestProgress';
import type { Locale } from './i18n';
import type { AuditEvent, Conversation, ConversationPage, RequestCase } from './types';
import './claim-trace.css';

type Relation = 'request' | 'transaction' | 'conversation' | 'product';
type Trace = {
  request: RequestCase; customer: { id: string; name: string }; observedAt: string; outcome: string;
  transaction: { id: string; productId: string; merchant: string; amountMinor: number; currency: string; status: string; date: string } | null;
  product: { id: string; cardKind?: CardKind | null; type: string; last4: string; status: string | null } | null;
  refund: { id: string; status: string; amountMinor: number; currency: string; destinationLast4: string; decisionNote: string | null; decidedAt: string | null; decidedBy: { id: string; name: string } | null; creditTransactionId: string | null } | null;
  documentCount: number | null;
  reviewContext?: { summary: Record<Locale, string>; missingEvidence: string[]; canStartReview: boolean; canDecideRefund: boolean; financialEffect: 'credited' | 'none' };
  events: (AuditEvent & { relation: Relation })[]; before: string | null; eventCount: number;
  conversations: (Conversation & { messageCount: number; relation: Relation })[]; conversationCount: number; nextConversationOffset: number | null;
};

export function ClaimTrace({ request, admin = false, compact = false, onChanged, refreshVersion = 0 }: { request: RequestCase; admin?: boolean; compact?: boolean; onChanged?: () => Promise<unknown>; refreshVersion?: number }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const navigate = useNavigate();
  const [openingCredit, setOpeningCredit] = useState(false);
  const [trace, setTrace] = useState<Trace | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const [tab, setTab] = useState<'detail' | 'evidence' | 'decision' | 'conversations' | 'documents' | 'activity' | 'json'>('detail');
  const [conversation, setConversation] = useState<ConversationPage | null>(null); const [conversationBusy, setConversationBusy] = useState(false); const [conversationError, setConversationError] = useState(false);
  const controller = useRef<AbortController | null>(null); const messageController = useRef<AbortController | null>(null);
  const path = admin ? `/admin/users/${encodeURIComponent(request.userId)}/requests/${encodeURIComponent(request.id)}/trace` : `/requests/${encodeURIComponent(request.id)}/trace`;
  const loadedPath = useRef(path);
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
  useEffect(() => {
    if (loadedPath.current !== path) { setTrace(null); setConversation(null); loadedPath.current = path; }
    void load();
    return () => { controller.current?.abort(); messageController.current?.abort(); };
  }, [path, request.updatedAt, request.refund?.status, refreshVersion]);
  async function viewConversation(id: string, before?: string) {
    messageController.current?.abort(); const control = new AbortController(); messageController.current = control;
    setConversationBusy(true); setConversationError(false); if (!before) setConversation(null);
    try {
      const value = await api<ConversationPage>((admin ? '/admin' : '') + '/conversations/' + encodeURIComponent(id) + (before ? '?before=' + encodeURIComponent(before) : ''), 'GET', undefined, control.signal);
      setConversation(old => ({ ...value, messages: before && old ? [...value.messages, ...old.messages] : value.messages }));
    } catch { if (!control.signal.aborted) setConversationError(true); }
    finally { if (!control.signal.aborted) setConversationBusy(false); }
  }
  const tt = (key:string, options:Record<string,unknown>={}) => t(request.kind==='application'?'application.'+key:key,options);
  const showSummary = !admin || tab === 'detail';
  const showEvidence = !admin || tab === 'evidence';
  const showDecision = !admin || tab === 'decision';
  const bodyRef = useRef<HTMLDivElement>(null);
  function selectTab(value: typeof tab) { setTab(value); bodyRef.current?.scrollTo({ top: 0 }); }
  async function changed() { await load(); await onChanged?.(); }
  async function openCredit(reference: string) {
    if (openingCredit) return;
    setOpeningCredit(true); setError(false);
    try { await onChanged?.(); navigate('/movements?transaction=' + encodeURIComponent(reference)); }
    catch { setError(true); }
    finally { setOpeningCredit(false); }
  }
  const showConversations = !admin || tab === 'conversations';
  const showActivity = !admin || tab === 'activity';
  const visibleEvents = trace?.events.filter(event => admin || ['created','claim_delivered','claim_approved','reviewed','handed_off','refund_requested','refund_approved','refund_rejected','card_blocked','conversation_linked','attention_resolved','attention_closed_by_timer','attention_closure_stopped','attention_reopened','feedback_submitted','feedback_draft_saved'].includes(event.action)) || [];
  const eventTitle = (action: string) => action.startsWith('navigate_') ? t('navigationRecorded', { screen: t(action.slice(9)) }) : t(action==='created'&&request.kind!=='application'?'claim.auditCreated':'auditActions.' + action, { defaultValue: t('trace.recordedActivity') });
  function eventDescription(action: string) {
    const key = action.startsWith('navigate_') ? 'navigation' : action;
    if(action==='created'&&request.kind!=='application')return t('claim.eventCreated');
    return tt('trace.event.' + key, { defaultValue: tt('trace.event.other') });
  }
  return <section className={'claim-trace ' + (compact ? 'compact' : '')} aria-label={t('trace.title')} data-trace-ready={!!trace && !busy}>
    <div className="trace-toolbar"><h2>{t('trace.title')}</h2><button className="button secondary" disabled={busy} onClick={() => void load()}><RefreshCw size={15} />{t('auditRefresh')}</button></div>
    {admin && <div className="trace-tabs" role="group" aria-label={t('trace.view')}>
      {(['detail', 'evidence', 'decision', 'conversations', 'documents', 'activity', 'json'] as const).map(item => <button key={item} data-trace-tab={item} aria-pressed={tab === item} onClick={() => selectTab(item)}>{t(item === 'detail' ? 'trace.simple' : item === 'evidence' ? 'inbox.evidence' : item === 'decision' ? 'inbox.manage' : item === 'json' ? 'inbox.technical' : 'caseAdmin.' + item)}{trace && item === 'conversations' && <span className="trace-count">{trace.conversationCount}</span>}{trace && item === 'documents' && <span className="trace-count">{trace.documentCount ?? 0}</span>}</button>)}
      <button className="trace-refresh" aria-label={t("auditRefresh")} disabled={busy} onClick={() => void load()}><RefreshCw size={16}/></button>
    </div>}
    <div className="trace-body" ref={bodyRef} tabIndex={admin ? 0 : undefined} role={admin ? "region" : undefined} aria-label={admin ? t("inbox.content") : undefined}>
    {busy && <p role="status">{t('loading')}</p>}{error && <p role="alert" className="error-text">{t('trace.error')}</p>}
    {trace && <> {admin && tab === 'json' && <pre className="trace-json" tabIndex={0} aria-label={t('trace.json')}>{JSON.stringify(trace, null, 2)}</pre>}
      <div hidden={!showSummary}>
      <div className="trace-current"><div><span className="eyebrow">{t('trace.now')}</span><h3>{tt('trace.outcome.' + trace.outcome)}</h3><p>{tt('trace.next.' + trace.outcome)}</p></div>{!compact && <RequestStatus request={trace.request} />}</div>

      {!admin && trace.refund?.creditTransactionId && <button className="button secondary case-credit-link" disabled={openingCredit} onClick={() => void openCredit(trace.refund!.creditTransactionId!)}>{t('caseDecision.viewCredit')}</button>}
      <dl className="trace-facts"><div><dt>{t('reference')}</dt><dd><code>{request.id}</code></dd></div><div><dt>{t('customer')}</dt><dd>{trace.customer.name}</dd></div><div><dt>{t('trace.receivedAt')}</dt><dd>{timestamp(trace.request.createdAt)}</dd></div><div><dt>{tt('trace.updatedAt')}</dt><dd>{timestamp(trace.request.updatedAt)}</dd></div></dl>
      {!admin && trace.request.handling?.note && <section className="trace-section"><h3>{t('claimStage.note')}</h3><p className="trace-text">{trace.request.handling.note}</p></section>}
      {!compact && <section className="trace-section"><h3><FileText size={18} />{t('trace.report')}</h3><p className="trace-text">{trace.request.details}</p></section>}
      {admin && trace.reviewContext && <section className="trace-section case-review-context"><h3>{t('caseDecision.context')}</h3><p className="trace-text">{trace.reviewContext.summary[locale] || t('caseDecision.noContext')}</p>{trace.reviewContext.missingEvidence.length > 0 && <><h4>{t('caseDecision.missing')}</h4><ul>{trace.reviewContext.missingEvidence.map(item => <li key={item}>{t('caseDecision.missing.' + item)}</li>)}</ul></>}<p className="muted">{t('caseDecision.evidenceLimit')}</p></section>}
      {admin && <div className="inbox-summary-actions"><button className="button secondary" onClick={() => selectTab('evidence')}>{t('inbox.reviewEvidence')}</button><button className="button primary" onClick={() => selectTab('decision')}>{t('inbox.manage')}</button></div>}
      </div><div hidden={!showEvidence}>
      <section className="trace-section"><h3>{t('trace.evidence')}</h3><p className="muted">{t('trace.evidenceHint')}</p>{trace.transaction ? <dl className="trace-facts">
        <div><dt>{t('linkedMovement')}</dt><dd><code>{trace.transaction.id}</code></dd></div><div><dt>{t('trace.merchant')}</dt><dd>{trace.transaction.merchant}</dd></div>
        <div><dt>{t('amount')}</dt><dd>{formatMoney(trace.transaction.amountMinor, locale, trace.transaction.currency)}</dd></div><div><dt>{t('status')}</dt><dd><Badge status={trace.transaction.status} /></dd></div>
        <div><dt>{t('date')}</dt><dd>{timestamp(trace.transaction.date)}</dd></div>{trace.product && <div><dt>{t('product')}</dt><dd>{t(productLabelKey(trace.product))} · •••• {trace.product.last4}{trace.product.status && <span> · {t(trace.product.status)}</span>}</dd></div>}
      </dl> : <p>{t('trace.noMovement')}</p>}</section>
      </div><div hidden={!showDecision}>
      {admin && !compact && <AdminCaseDecision request={trace.request} onChanged={changed}/>}
      {!compact && trace.refund && <section className="trace-section"><h3>{t('trace.decision')}</h3><dl className="trace-facts"><div><dt>{t('operationId')}</dt><dd><code>{trace.refund.id}</code></dd></div><div><dt>{t('status')}</dt><dd>{t('refundStatus.' + trace.refund.status)}</dd></div><div><dt>{t('amount')}</dt><dd>{formatMoney(trace.refund.amountMinor, locale, trace.refund.currency)}</dd></div><div><dt>{t('refundDestination')}</dt><dd>•••• {trace.refund.destinationLast4}</dd></div>
        {trace.refund.decidedBy && <div><dt>{t('auditActor')}</dt><dd>{trace.refund.decidedBy.name}</dd></div>}{trace.refund.decidedAt && <div><dt>{t('date')}</dt><dd>{timestamp(trace.refund.decidedAt)}</dd></div>}{trace.refund.creditTransactionId && <div><dt>{t('refundCreditReference')}</dt><dd><code>{trace.refund.creditTransactionId}</code></dd></div>}</dl>
        {trace.refund.decisionNote && <div className="trace-decision"><strong>{t('refundEvidence')}</strong><p className="trace-text">{trace.refund.decisionNote}</p></div>}<p className="muted">{tt('trace.separateStatus', { status: t(trace.request.status) })}</p></section>}
      <AttentionReview refreshKey={trace.observedAt} source="requests" identity={request.id} admin={admin} onChange={() => void load()}/>
      </div>
      {admin && tab === 'documents' && <AdminCaseDocuments userId={request.userId} requestId={request.id} />}
      {showConversations && <section className="trace-section"><h3><MessageCircle size={18} />{t('trace.conversations')} <span className="trace-count">{trace.conversationCount}</span></h3><p className="muted">{t('trace.conversationHint')}</p>
        {!trace.conversations.length && <p>{t(admin ? 'trace.noConversations' : 'trace.noOwnConversations')}</p>}<div className="trace-conversations">{trace.conversations.map(c => <button className="trace-conversation" key={c.id} disabled={conversationBusy} onClick={() => void viewConversation(c.id)} aria-label={t('trace.openConversation', { title: c.title || t('previousConversation') })}><strong>{c.title || t('previousConversation')}</strong><span>{timestamp(c.updatedAt)} · {t('trace.messageCount', { count: c.messageCount })}</span><small>{tt('trace.relation.' + c.relation)} · {c.locale.toUpperCase()}</small></button>)}</div>
        {trace.nextConversationOffset !== null && <button className="text-link" disabled={busy} onClick={() => void load('conversations')}>{t('loadMore')}</button>}
        {conversationBusy && <p role="status">{t('loading')}</p>}{conversationError && <p role="alert" className="error-text">{t('trace.error')}</p>}
        {conversation && <section className="trace-transcript" aria-label={t('conversation')}><div className="trace-toolbar"><strong>{t('conversation')}</strong><button className="text-link" onClick={() => { messageController.current?.abort(); setConversationBusy(false); setConversation(null); }}>{t('close')}</button></div><p className="muted">{t('trace.originalLanguage')}</p>
          {conversation.before && <button className="text-link" disabled={conversationBusy} onClick={() => void viewConversation(conversation.conversation.id, conversation.before!)}>{t('olderMessages')}</button>}
          {conversation.flow && (admin ? <details className="case-engine-details"><summary>{t('caseAdmin.engineDetails')}</summary><ChatFlow readOnly technical result={conversation.flow} conversationId={conversation.conversation.id} text="" onRegistered={() => {}}/></details> : <ChatFlow readOnly technical={false} result={conversation.flow} conversationId={conversation.conversation.id} text="" onRegistered={() => {}}/>)}{conversation.messages.map(m => <article className={'trace-message ' + m.role} key={m.id}><strong>{t(m.role === 'user' ? 'customer' : 'assistant')}</strong><time dateTime={m.at}>{timestamp(m.at)}</time><p className="trace-text" lang={m.locale}>{m.text}</p></article>)}</section>}
      </section>}
      {showActivity && <section className="trace-section"><h3><Clock3 size={18} />{t('trace.activity')} {admin && <span className="trace-count">{trace.eventCount}</span>}</h3><p className="muted">{request.kind==='application'?tt('trace.activityHint'):t('claim.activityHint')}</p>
        <ol className="trace-events">{visibleEvents.map(e => <li key={e.id}><span className="trace-event-icon"><Check size={14} /></span><article><div className="trace-event-heading"><strong>{eventTitle(e.action)}</strong><time dateTime={e.at}>{timestamp(e.at)}</time></div><p>{eventDescription(e.action)}</p><div className="trace-event-meta"><span>{t('auditActor')}: {e.actorName}</span><span>{tt('trace.relation.' + e.relation)}</span></div>{admin && <details><summary>{t('trace.references')}</summary><dl><div><dt>{t('trace.auditId')}</dt><dd><code>{e.id}</code></dd></div>{e.transactionId && <div><dt>{t('linkedMovement')}</dt><dd><code>{e.transactionId}</code></dd></div>}{e.conversationId && <div><dt>{t('conversation')}</dt><dd><code>{e.conversationId}</code></dd></div>}<div><dt>{t('trace.eventCode')}</dt><dd><code>{e.action}</code></dd></div></dl></details>}</article></li>)}</ol>
        {!visibleEvents.length && <p>{t('trace.noEvents')}</p>}{trace.before && <button className="button secondary" disabled={busy} onClick={() => void load('events')}>{t('trace.olderEvents')}</button>}
      </section>}<p className="trace-source">{t('trace.observed', { date: timestamp(trace.observedAt) })}</p>
    </>}
    </div>
  </section>;
}
