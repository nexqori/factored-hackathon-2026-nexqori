import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Headphones, History, MessageCircle, Plus, Phone } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { Dialog } from './components';
import { PasteComposer } from './PasteComposer';
import { localeTags, type Locale } from './i18n';
import type { Destination, NavigationCommand } from './navigation';
import type { Conversation, ConversationList, ConversationPage, Message } from './types';

export type ChatReply = { text: string; destination: string | null; navigation: NavigationCommand | null; conversation: Conversation; messages: Message[] };
export function Bot({ large = false }: { large?: boolean }) { return <img className={'bot-avatar' + (large ? ' bot-large' : '')} src="/nexqori-bot.png" alt="" aria-hidden="true" width={large ? 100 : 48} height={large ? 100 : 48} />; }

export function AssistantPanel({ currentPage, onReply, guided = false }: { guided?: boolean; currentPage: Destination; onReply: (reply: ChatReply) => void }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language as Locale;
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const conversationId = useRef<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [before, setBefore] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState(false);
  const [voice, setVoice] = useState(false);
  const [historyItems, setHistoryItems] = useState<Conversation[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const request = useRef<AbortController | null>(null);
  const page = useRef(currentPage); page.current = currentPage;
  const replyHandler = useRef(onReply); replyHandler.current = onReply;
  const log = useRef<HTMLDivElement>(null);
  function fail(e: unknown) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (log.current) log.current.scrollTop = log.current.scrollHeight; }, [messages.at(-1)?.id]);

  async function send(message: string, signal?: AbortSignal, pastedText=''): Promise<string> {
    if (busyRef.current || (!message.trim()&&!pastedText.trim())) throw new ApiError('conflict', 409);
    busyRef.current = true; setBusy(true); setError('');
    const controller = new AbortController(); request.current = controller;
    const abort = () => controller.abort(); signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) controller.abort();
    try {
      const result = await api<ChatReply>('/assistant', 'POST', { message: message.trim(), pastedText, locale, currentPage: page.current, conversationId: conversationId.current }, controller.signal);
      if (controller.signal.aborted) return '';
      conversationId.current = result.conversation.id; setConversation(result.conversation);
      setMessages(items => [...items, ...result.messages]);
      replyHandler.current(result);
      return result.text;
    } finally { signal?.removeEventListener('abort', abort); busyRef.current = false; setBusy(false); }
  }
  function submit(message: string) { void send(message).catch(fail); }
  async function fetchHistory(offset = 0) {
    setHistoryBusy(true); setError('');
    try { const result = await api<ConversationList>('/conversations?offset=' + offset); setHistoryItems(items => offset ? [...items, ...result.conversations] : result.conversations); setNextOffset(result.nextOffset); }
    catch (e) { fail(e); }
    finally { setHistoryBusy(false); }
  }
  const [composerKey,setComposerKey]=useState(0);
  function fresh() { conversationId.current = null; setConversation(null); setMessages([]); setBefore(null); setComposerKey(k=>k+1); setError(''); setHistory(false); }
  async function select(item: Conversation) {
    setHistoryBusy(true); setError('');
    try { const result = await api<ConversationPage>('/conversations/' + item.id); conversationId.current = result.conversation.id; setConversation(result.conversation); setMessages(result.messages); setBefore(result.before); setComposerKey(k=>k+1); setHistory(false); }
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
  const formatTime = (value: string) => new Intl.DateTimeFormat(localeTags[locale], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  return <aside className="assistant-panel" aria-label={t('assistant')}>
    <div className="assistant-header"><Bot /><div><h2>{t('assistant')}</h2><p>{t('guided')}</p></div></div>
    <div className="conversation-toolbar"><button disabled={busy} onClick={fresh}><Plus size={16} />{t('newConversationShort')}</button><button disabled={busy} onClick={() => { setHistory(true); void fetchHistory(); }}><History size={16} />{t('conversations')}</button></div>
    <button className="voice-entry" disabled={busy} onClick={()=>setVoice(true)}><Phone size={16}/>{t('startVoice')}</button>
    {voice&&<Dialog title={t('voiceTitle')} onClose={()=>setVoice(false)}><div className="voice-preview"><Bot large/><span className="round-icon"><Phone size={26}/></span><p>{t('voiceSoon')}</p><button className="button primary wide" onClick={()=>setVoice(false)}>{t('voiceContinue')}</button></div></Dialog>}
    {conversation && <div className="conversation-current" title={title}><MessageCircle size={13} /><span lang={conversation.title ? conversation.locale : locale}>{title}</span></div>}
    <div ref={log} className="chat-messages" tabIndex={0} aria-label={t('conversation')} role="log" aria-live="polite" aria-relevant="additions">
      {!messages.length && <><div className="assistant-welcome"><Bot large /><h3>{t('assistantHello')}</h3><p>{t(guided ? 'guidedConversationWelcome' : 'conversationWelcome')}</p></div><div className="chat-suggestions"><p className="eyebrow">{t('suggestions')}</p>{['askSaldo', 'askNavigate', 'askUnknown', 'askTrack'].map(key => <button key={key} disabled={busy} onClick={() => submit(t(key))}>{t(key)}<ArrowUpRight size={15} /></button>)}</div></>}
      {before && <button className="text-link older-messages" disabled={busy} onClick={() => { void older(); }}>{t('olderMessages')}</button>}
      {messages.map(message => <div className={'chat-bubble ' + message.role} key={message.id} lang={message.locale}>{message.text}</div>)}{busy && <p className="chat-thinking" role="status">{t('loading')}</p>}
    </div>
    {error && !history && <p className="error-text assistant-error" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}
    <div className="chat-bottom"><PasteComposer key={composerKey} busy={busy} onSend={(message,pasted)=>send(message,undefined,pasted)} copy={{text:t('pastedText'),preview:t('previewPasted'),remove:t('removePasted'),placeholder:t('chatPlaceholder'),label:t('chatLabel'),send:t('send'),limit:t('pasteLimit'),failed:t('error.generic')}}/><button className="human-link" disabled={busy} onClick={() => submit(t('talkHuman'))}><Headphones size={15} />{t('talkHuman')}</button></div>
    {history && <Dialog title={t('conversations')} onClose={() => setHistory(false)} busy={historyBusy}><p className="muted">{t('historyIntro')}</p><button className="button secondary wide history-new" disabled={historyBusy} onClick={fresh}><Plus size={18} />{t('newConversation')}</button>{error && <p className="error-text" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}<div className="conversation-list">{historyItems.map(item => <button className={item.id === conversationId.current ? 'current' : ''} key={item.id} disabled={historyBusy} onClick={() => { void select(item); }}><MessageCircle size={18} /><span><strong lang={item.title ? item.locale : locale}>{item.title || t('previousConversation')}</strong><time>{formatTime(item.updatedAt)}</time></span><ArrowUpRight size={17} /></button>)}</div>{!historyItems.length && !historyBusy && !error && <p className="empty-copy">{t('noConversations')}</p>}{historyBusy && <p role="status">{t('loading')}</p>}{nextOffset !== null && <button className="text-link" disabled={historyBusy} onClick={() => { void fetchHistory(nextOffset); }}>{t('loadMore')}</button>}</Dialog>}
  </aside>;
}
