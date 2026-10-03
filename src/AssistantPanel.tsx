import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Headphones, History, MessageCircle, Plus, Phone, Info } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { Dialog, formatDate, formatMoney } from './components';
import { type FlowResult } from './ChatFlow';
import { ChatDetails, type ChatSelection } from './ChatDetails';
import { VoiceCall } from './VoiceCall';
import { ChatDocuments, DocumentDownload } from './ChatDocuments';
import type { Dashboard } from './types';
import { PasteComposer } from './PasteComposer';
import { localeTags, type Locale } from './i18n';
import type { Destination, NavigationCommand } from './navigation';
import type { Conversation, ConversationList, ConversationPage, Message } from './types';

export type ChatReply = { flow?: FlowResult; text: string; destination: string | null; navigation: NavigationCommand | null; conversation: Conversation; messages: Message[] };
export type TransactionQuestion = { nonce: string; transactionId: string; merchant: string };
export function Bot({ large = false }: { large?: boolean }) { return <img className={'bot-avatar' + (large ? ' bot-large' : '')} src="/nexqori-bot.png" alt="" aria-hidden="true" width={large ? 100 : 48} height={large ? 100 : 48} />; }

export function AssistantPanel({ currentPage, onReply, guided = false, transactionQuestion, data, onClaim }: { data: Dashboard; onClaim: (id: string) => void; guided?: boolean; currentPage: Destination; onReply: (reply: ChatReply) => void; transactionQuestion?: TransactionQuestion | null }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language as Locale;
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const conversationId = useRef<string | null>(null);
  const [connected, setConnected] = useState(true); const [configured, setConfigured] = useState(true);
  const [flow, setFlow] = useState<FlowResult | null>(null); const [selectedTx, setSelectedTx] = useState(''); const [selectedRequest, setSelectedRequest] = useState('');
  const attempt = useRef<{signature: string; key: string} | null>(null);
  useEffect(() => { const c = new AbortController(); void api<{connected: boolean; providers: Record<string,string>}>('/assistant/capabilities','GET',undefined,c.signal).then(r => { setConnected(r.connected); setConfigured(!r.connected || Object.values(r.providers).every(v => v === 'configured')); }).catch(() => {}); return () => c.abort(); }, []);
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<{text:string; locale:Locale} | null>(null);
  const [before, setBefore] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState(false);
  const [voice, setVoice] = useState(false);
  const [documentsOpen,setDocumentsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  function openDetails() { setDetailsOpen(true); }
  const [historyItems, setHistoryItems] = useState<Conversation[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const page = useRef(currentPage); page.current = currentPage;
  const replyHandler = useRef(onReply); replyHandler.current = onReply;
  const log = useRef<HTMLDivElement>(null);
  const handledTransaction = useRef<string | null>(null);
  function fail(e: unknown) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages.at(-1)?.id, pending, busy]);

  async function send(message: string, signal?: AbortSignal, pastedText='', transactionId?: string, replaceTransaction=false, selection?: ChatSelection): Promise<string> {
    if (voice || busyRef.current || (!message.trim()&&!pastedText.trim())) throw new ApiError('conflict', 409);
    busyRef.current = true; setBusy(true); setError('');
    setPending({text: [message.trim(), pastedText.trim() ? t('pastedText') + '\n' + pastedText : ''].filter(Boolean).join('\n\n'), locale});
    const controller = new AbortController(); request.current = controller;
    const abort = () => controller.abort(); signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    try {
      const body = { message: message.trim(), pastedText, locale, currentPage: page.current, conversationId: conversationId.current, ...((transactionId || selectedTx) ? {transactionId: transactionId || selectedTx} : {}), ...(replaceTransaction ? {replaceTransaction:true} : {}), ...(connected && selectedRequest && !replaceTransaction ? {requestId:selectedRequest} : {}) };
      const selectedBody = selection ? {...body, transactionId:selection.transactionId || null, requestId:selection.requestId || null, updateSelection:true} : body;
      const signature = JSON.stringify(selectedBody);
      if (attempt.current?.signature !== signature) attempt.current = {signature, key:crypto.randomUUID()};
      const result = await api<ChatReply>(connected ? '/assistant/flow' : '/assistant', 'POST', {...selectedBody, ...(connected ? {requestKey:attempt.current.key} : {})}, controller.signal);
      attempt.current = null; setFlow(result.flow || null);
      if (controller.signal.aborted) return '';
      conversationId.current = result.conversation.id; setConversation(result.conversation);
      setSelectedTx(result.conversation.transactionId || '');
      setSelectedRequest(result.flow?.selectedRequestId || '');
      setMessages(items => [...items, ...result.messages.filter(m => !items.some(old => old.id === m.id))]);
      replyHandler.current(result);
      return result.text;
    } finally { signal?.removeEventListener('abort', abort); busyRef.current = false; setBusy(false); setPending(null); }
  }
  function submit(message: string) { void send(message).catch(fail); }
  async function applySelection(selection: ChatSelection) {
    if (flow?.requestId) throw new ApiError('conflict',409);
    if (!conversationId.current) { setSelectedTx(selection.transactionId); setSelectedRequest(selection.requestId); return; }
    if (selectedTx === selection.transactionId && selectedRequest === selection.requestId) return;
    const key = selection.transactionId ? selection.requestId ? 'bothMessage' : 'movementMessage' : selection.requestId ? 'caseMessage' : 'noneMessage';
    await send(t('chatSelection.' + key),undefined,'',undefined,false,selection);
  }
  async function fetchHistory(offset = 0) {
    setHistoryBusy(true); setError('');
    try { const result = await api<ConversationList>('/conversations?offset=' + offset); setHistoryItems(items => offset ? [...items, ...result.conversations] : result.conversations); setNextOffset(result.nextOffset); }
    catch (e) { fail(e); }
    finally { setHistoryBusy(false); }
  }
  const [composerKey,setComposerKey]=useState(0);
  function fresh() { setDocumentsOpen(false); setDetailsOpen(false); setFlow(null); setSelectedTx(''); setSelectedRequest(''); attempt.current = null; conversationId.current = null; setConversation(null); setMessages([]); setBefore(null); setComposerKey(k=>k+1); setError(''); setHistory(false); }
  useEffect(() => {
    if (!transactionQuestion || voice || busy || historyBusy || handledTransaction.current === transactionQuestion.nonce) return;
    handledTransaction.current = transactionQuestion.nonce;
    fresh(); setSelectedTx(transactionQuestion.transactionId);
    void send(t('askTransactionQuestion', { id: transactionQuestion.transactionId, merchant: transactionQuestion.merchant }), undefined, '', transactionQuestion.transactionId).catch(fail);
  }, [transactionQuestion, voice, busy, historyBusy]);
  async function select(item: Conversation) {
    setHistoryBusy(true); setError('');
    try { const result = await api<ConversationPage>('/conversations/' + item.id); conversationId.current = result.conversation.id; setConversation(result.conversation); setMessages(result.messages); setBefore(result.before); setSelectedTx(result.conversation.transactionId || ''); const loadedFlow = (await api<{flow:FlowResult|null}>('/conversations/' + item.id + '/flow')).flow; setFlow(loadedFlow); setSelectedRequest(loadedFlow?.selectedRequestId || ''); setComposerKey(k=>k+1); setHistory(false); }
    catch (e) { fail(e); }
    finally { setHistoryBusy(false); }
  }
  async function older() {
    setBusy(true); busyRef.current = true; setError('');
    try { const result = await api<ConversationPage>('/conversations/' + conversationId.current + '?before=' + before); setMessages(items => [...result.messages, ...items]); setBefore(result.before); }
    catch (e) { fail(e); }
    finally { setBusy(false); busyRef.current = false; }
  }
  const title = conversation?.title || t(conversation ? 'previousConversation' : 'newConversation');
  const selectedTransaction = data.transactions.find(tx => tx.id === selectedTx);
  const formatTime = (value: string) => new Intl.DateTimeFormat(localeTags[locale], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  return <aside className="assistant-panel" aria-label={t('assistant')}>
    <div className="assistant-header"><Bot /><div><h2>{t('assistant')}</h2><p>{t('guided')}</p></div>{connected && <button className="chat-details-button" disabled={voice} aria-haspopup="dialog" onClick={() => openDetails()}><Info size={16}/>{t('chatDetails.open')}</button>}</div>
    <div className="conversation-toolbar"><button disabled={busy || voice} onClick={fresh}><Plus size={16} />{t('newConversationShort')}</button><button disabled={busy || voice} onClick={() => { setHistory(true); void fetchHistory(); }}><History size={16} />{t('conversations')}</button></div>
    <button className="voice-entry" disabled={busy || voice} onClick={()=>setVoice(true)}><Phone size={16}/>{t('startVoice')}</button>
    {voice&&<VoiceCall onSession={id=>{conversationId.current=id;}} selection={{conversationId:conversationId.current,transactionId:selectedTx||null,requestId:selectedRequest||null,locale}} onReply={result=>{conversationId.current=result.conversation.id;setConversation(result.conversation);setFlow(result.flow||null);setSelectedTx(result.conversation.transactionId||'');setSelectedRequest(result.flow?.selectedRequestId||'');setMessages(items=>[...items,...result.messages.filter(m=>!items.some(old=>old.id===m.id))]);replyHandler.current(result);}} onClose={()=>setVoice(false)}/>}
    {conversation && <div className="conversation-current" title={title}><MessageCircle size={13} /><span lang={conversation.title ? conversation.locale : locale}>{title}</span></div>}
    <div ref={log} className="chat-messages" tabIndex={0} aria-label={t('conversation')} role="log" aria-live="polite" aria-relevant="additions">
      {!messages.length && !pending && <><div className="assistant-welcome"><Bot large /><h3>{t('assistantHello')}</h3><p>{t(guided ? 'guidedConversationWelcome' : 'conversationWelcome')}</p></div><div className="chat-suggestions"><p className="eyebrow">{t('suggestions')}</p>{['askSaldo', 'askNavigate', 'askUnknown', 'askTrack'].map(key => <button key={key} disabled={busy || voice} onClick={() => submit(t(key))}>{t(key)}<ArrowUpRight size={15} /></button>)}</div></>}
      {before && <button className="text-link older-messages" disabled={busy} onClick={() => { void older(); }}>{t('olderMessages')}</button>}
      {messages.map(message => <div className={'chat-bubble ' + message.role} key={message.id} lang={message.locale}>{message.text}{message.document&&<DocumentDownload document={message.document}/>}</div>)}
      {pending && <div className="chat-bubble user chat-pending" lang={pending.locale}>{pending.text}</div>}
      {busy && <div className="chat-thinking" role="status"><span className="thinking-dots" aria-hidden="true"><i/><i/><i/></span>{t(pending ? 'chatSending.thinking' : 'loading')}</div>}
      {!busy && connected && !flow?.requestId && (messages.length > 0 || !!selectedTx) && <div className="chat-movement-context">
        {selectedTransaction && !flow?.canRegister && <div className="chat-selected-movement" data-chat-movement={selectedTx}><strong>{selectedTransaction.merchant}</strong><span>{formatMoney(selectedTransaction.amountMinor,locale,selectedTransaction.currency)} · {formatDate(selectedTransaction.date,locale)}</span><small>{t('chatMovement.reference')}: {selectedTx}</small></div>}
        {!selectedTx && <div className="chat-transaction-choice" aria-label={t('chatSending.suggestion')}>
          {flow?.suggestedTransaction && !selectedTx && <button className="button primary" disabled={voice} onClick={() => { void send(t('chatSending.confirmMessage'),undefined,'',flow.suggestedTransaction!.id).catch(fail); }}>{t('chatSending.confirm')}</button>}
          <button className="button secondary" disabled={voice} aria-haspopup="dialog" onClick={() => openDetails()}>{t('chatMovement.choose')}</button>
        </div>}
      </div>}
      {!busy && flow?.canDocument && conversation && <button className="button secondary chat-next-action" disabled={voice} onClick={()=>setDocumentsOpen(true)}>{t('documents.prepare')}</button>}
      {!busy && flow?.canRegister && <button className="button secondary chat-next-action" disabled={voice} onClick={() => openDetails()}>{t('chatFlow.prepareClaim')}<ArrowUpRight size={16}/></button>}
      {!busy && flow?.missing_fields.includes('request_id') && <button className="text-link chat-next-action" disabled={voice} onClick={() => openDetails()}>{t('chatDetails.selectRecords')}<ArrowUpRight size={16}/></button>}
    </div>
    {error && !history && <p className="error-text assistant-error" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}
    {connected && !configured && <p className="flow-provider-warning">{t('chatFlow.unconfigured')}</p>}
    {documentsOpen && conversation && <ChatDocuments conversationId={conversation.id} data={data} onClose={()=>setDocumentsOpen(false)} onMessage={m=>setMessages(items=>items.some(x=>x.id===m.id)?items:[...items,m])}/>}
    {detailsOpen && <ChatDetails result={flow} conversation={conversation} data={data} selectedTx={selectedTx} selectedRequest={selectedRequest} onApply={applySelection} busy={busy || voice} onClose={() => setDetailsOpen(false)} onRegistered={claim => { setFlow(claim.flow); setMessages(items=>items.some(m=>m.id===claim.message.id)?items:[...items,claim.message]); setDetailsOpen(false); onClaim(claim.id); }}/>}
    <div className="chat-bottom"><PasteComposer key={composerKey} busy={busy || voice} onSend={(message,pasted)=>send(message,undefined,pasted)} copy={{text:t('pastedText'),preview:t('previewPasted'),remove:t('removePasted'),placeholder:t('chatPlaceholder'),label:t('chatLabel'),send:t('send'),limit:t('pasteLimit'),failed:t('chatSending.failed')}}/><button className="human-link" disabled={busy || voice} onClick={() => submit(t('talkHuman'))}><Headphones size={15} />{t('talkHuman')}</button></div>
    {history && <Dialog title={t('conversations')} onClose={() => setHistory(false)} busy={historyBusy}><p className="muted">{t('historyIntro')}</p><button className="button secondary wide history-new" disabled={historyBusy} onClick={fresh}><Plus size={18} />{t('newConversation')}</button>{error && <p className="error-text" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}<div className="conversation-list">{historyItems.map(item => <button className={item.id === conversationId.current ? 'current' : ''} key={item.id} disabled={historyBusy} onClick={() => { void select(item); }}><MessageCircle size={18} /><span><strong lang={item.title ? item.locale : locale}>{item.title || t('previousConversation')}</strong><time>{formatTime(item.updatedAt)}</time></span><ArrowUpRight size={17} /></button>)}</div>{!historyItems.length && !historyBusy && !error && <p className="empty-copy">{t('noConversations')}</p>}{historyBusy && <p role="status">{t('loading')}</p>}{nextOffset !== null && <button className="text-link" disabled={historyBusy} onClick={() => { void fetchHistory(nextOffset); }}>{t('loadMore')}</button>}</Dialog>}
  </aside>;
}
