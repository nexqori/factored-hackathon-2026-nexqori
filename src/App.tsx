import { useEffect, useRef, useState, type FormEvent } from 'react';
import { BrowserRouter, NavLink, Route, Routes, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowRight, ArrowUpRight, Bell, ChevronDown, CreditCard, Eye, EyeOff, Headphones, Home, LayoutGrid, LogOut, Menu, MessageCircle, Plus, Search, Send, ShieldCheck, Sparkles, Wallet, FileText, CircleHelp, Volume2, Check, Globe2, LockKeyhole, ArrowLeftRight, Landmark, ChartNoAxesCombined, Umbrella, Banknote, Type, RefreshCw, X } from 'lucide-react';
import i18n, { locales, isLocale, type Locale } from './i18n';
import { api, ApiError, setCsrf } from './api';
import { Brand, Badge, Dialog, TransactionList, formatMoney, formatDate } from './components';
import { destinations, currentDestination, safeNavigation, type NavigationCommand } from './navigation';
import { intentDestinations, isRoutedIntent, navigateForIntent } from './intent-router';
import { scheduleChatFeedback } from './chat-session';
import { chatSurveyScores, chooseChatSurvey, type ChatSurveyMetric } from './chat-survey';
import type { User, Dashboard, AdminData, Transaction, RequestCase, Service } from './types';

const languageLabels = { es: 'Español', en: 'English', pt: 'Português' };
const empty: Dashboard = { products: [], transactions: [], requests: [], audit: [], messages: [] };
const navigation = [{ path: '/', label: 'home', Icon: Home }, { path: '/movements', label: 'movements', Icon: ArrowLeftRight }, { path: '/products', label: 'products', Icon: Wallet }, { path: '/services', label: 'services', Icon: LayoutGrid }, { path: '/requests', label: 'requests', Icon: FileText }];
const serviceItems: { id: Exclude<Service, 'general' | 'support'>; Icon: typeof Wallet }[] = [{ id: 'accounts', Icon: Wallet }, { id: 'cards', Icon: CreditCard }, { id: 'transfers', Icon: ArrowLeftRight }, { id: 'payments', Icon: Landmark }, { id: 'loans', Icon: Home }, { id: 'investments', Icon: ChartNoAxesCombined }, { id: 'insurance', Icon: Umbrella }, { id: 'cash', Icon: Banknote }];
type Modal = { type: 'transaction'; transaction: Transaction } | { type: 'request'; id: string } | { type: 'create'; transactionId?: string; service?: Service } | { type: 'handoff'; id: string } | { type: 'review'; id: string };
function errorText(error: unknown) { const key = error instanceof ApiError ? 'error.' + error.code : 'error.generic'; return i18n.t(i18n.exists(key) ? key : 'error.generic'); }
function formatNumber(value: number, maximumFractionDigits = 2) { return new Intl.NumberFormat(i18n.language, { maximumFractionDigits }).format(value); }
function formatDuration(milliseconds: number | null) { return milliseconds === null ? '—' : milliseconds < 60000 ? i18n.t('secondsValue', { value: Math.round(milliseconds / 1000) }) : i18n.t('minutesValue', { value: formatNumber(milliseconds / 60000, 1) }); }

function LanguagePicker({ onChange }: { onChange: (locale: Locale) => void }) {
  const { t, i18n } = useTranslation();
  return <label className="language-picker"><Globe2 size={16} aria-hidden="true" /><span className="sr-only">{t('language')}</span><select aria-label={t('language')} value={i18n.language} onChange={e => { if (isLocale(e.target.value)) onChange(e.target.value); }}>{locales.map(locale => <option key={locale} value={locale}>{languageLabels[locale]}</option>)}</select></label>;
}
function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const { t } = useTranslation(); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function submit(event: FormEvent) { event.preventDefault(); if (busy) return; setError(''); setBusy(true); try { const data = await api<{ user: User; csrfToken: string }>('/auth/login', 'POST', { email, password }); setCsrf(data.csrfToken); const chosen = i18n.language as Locale; await api('/profile/locale', 'PATCH', { locale: chosen }); onLogin({ ...data.user, locale: chosen }); setPassword(''); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  return <div className="login-page"><section className="login-story"><Brand light /><div className="story-content"><span className="eyebrow">NEXQORI</span><h1>{t('loginFeature')}</h1><p>{t('loginDescription')}</p><div className="story-orbit" aria-hidden="true"><span className="orbit-ring" /><span className="orbit-ring second" /><span className="orbit-logo">n.</span><span className="orbit-tile"><Wallet size={26} /></span><span className="orbit-tile second"><MessageCircle size={26} /></span></div></div><p className="story-footer">{t('tagline')}</p></section>
    <section className="login-main"><div className="login-language"><LanguagePicker onChange={locale => { void i18n.changeLanguage(locale); }} /></div><div className="login-form-wrap"><span className="round-icon"><LockKeyhole size={24} /></span><h2>{t('loginTitle')}</h2><p>{t('loginSubtitle')}</p><form onSubmit={submit} className="form-stack"><label>{t('email')}<input type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="username" required maxLength={254} /></label><label>{t('password')}<input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" required maxLength={256} /></label>{error && <p className="error-text" role="alert">{error}</p>}<button className="button primary wide" disabled={busy}>{busy ? t('loading') : t('signIn')}<ArrowRight size={18} /></button></form><p className="login-note"><ShieldCheck size={17} />{t('loginNote')}</p><div className="login-benefits"><span>{t('loginBenefitTitle')}</span><p>{t('loginBenefitBody')}</p></div></div></section>
  </div>;
}

function CreateRequest({ modal, data, close, saved }: { modal: Extract<Modal, { type: 'create' }>; data: Dashboard; close: () => void; saved: (id: string, duplicate: boolean) => Promise<void> }) {
  const { t, i18n } = useTranslation(); const [transactionId, setTransactionId] = useState(modal.transactionId || ''); const [reason, setReason] = useState(modal.transactionId ? 'unknown' : 'other'); const [details, setDetails] = useState(modal.service ? t('servicePrefill', { service: t(modal.service) }) : ''); const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [requestKey] = useState(() => crypto.randomUUID());
  async function submit(e: FormEvent) { e.preventDefault(); setError(''); if (!confirmed) { setError(t('confirmationError')); return; } if (details.trim().length < 10) { setError(t('error.details')); return; } setBusy(true); try { const result = await api<{ id: string; duplicate: boolean }>('/requests', 'POST', { transactionId: transactionId || null, requestKey, service: modal.service || 'general', reason, details, confirmed }); await saved(result.id, result.duplicate); } catch (e) { setError(errorText(e)); } finally { setBusy(false); } }
  return <Dialog title={t('newRequest')} onClose={close} busy={busy}><p className="muted">{t('requestExplain')}</p><form className="form-stack" onSubmit={submit}>
    <label>{t('chooseTransaction')}<select value={transactionId} onChange={e => setTransactionId(e.target.value)}><option value="">{t('noTransaction')}</option>{data.transactions.map(tx => <option key={tx.id} value={tx.id}>{tx.merchant} · {formatMoney(tx.amountMinor, i18n.language as Locale)}</option>)}</select></label>
    <label>{t('reason')}<select value={reason} onChange={e => setReason(e.target.value)}>{['unknown', 'amount', 'payment', 'other'].map(value => <option value={value} key={value}>{t(value === 'amount' ? 'amountReason' : value)}</option>)}</select></label>
    <label>{t('detailLabel')}<textarea rows={4} value={details} onChange={e => setDetails(e.target.value)} placeholder={t('detailPlaceholder')} minLength={10} maxLength={1000} required aria-describedby="details-hint" /></label><small className="muted" id="details-hint">{t('characters')}</small>
    <label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />{t('confirmCheck')}</label>
    {error && <p className="error-text" role="alert">{error}</p>}<div className="dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={close}>{t('cancel')}</button><button className="button primary" disabled={busy}>{busy ? t('loading') : t('confirm')}<ArrowRight size={17} /></button></div>
  </form></Dialog>;
}

function Shell({ user, setUser, signOut }: { user: User; setUser: (user: User) => void; signOut: () => Promise<void> }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale; const navigate = useNavigate(); const location = useLocation();
  const emptyFeedbackMetric: AdminData['chatFeedback']['nps'] = { responses: 0, averageScore: null, npsScore: null, csatPercent: null, averageFormDurationMs: null, averageConversationDurationMs: null };
  const [data, setData] = useState<Dashboard>(empty); const [adminData, setAdminData] = useState<AdminData>({ users: [], requests: [], audit: [], chatFeedback: { nps: emptyFeedbackMetric, csat: emptyFeedbackMetric, ces: emptyFeedbackMetric } }); const [loading, setLoading] = useState(true); const [loadError, setLoadError] = useState(''); const [notice, setNotice] = useState(''); const [actionError, setActionError] = useState(''); const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<Modal | null>(null); const [search, setSearch] = useState(''); const [filter, setFilter] = useState('all'); const [hidden, setHidden] = useState(false); const [large, setLarge] = useState(false); const [menu, setMenu] = useState(false); const [chat, setChat] = useState(''); const [chatBusy, setChatBusy] = useState(false);
  const [chatSurvey, setChatSurvey] = useState<ChatSurveyMetric | null>(null); const [surveyScore, setSurveyScore] = useState<number | null>(null); const [surveyBusy, setSurveyBusy] = useState(false); const [conversationActive, setConversationActive] = useState(false); const [chatActivity, setChatActivity] = useState(0); const [hiddenChatMessages, setHiddenChatMessages] = useState<Set<string>>(() => new Set());
  const chatInput = useRef<HTMLInputElement>(null); const chatLog = useRef<HTMLDivElement>(null);
  const conversationStartedAt = useRef<number | null>(null); const surveyPromptedAt = useRef<number | null>(null);
  const surveySubmissionId = useRef<string | null>(null);
  const visibleMessages = data.messages.filter(message => !hiddenChatMessages.has(message.id));
  async function refresh() { const next = await api<Dashboard>('/bootstrap'); setData(next); if (user.role === 'admin') setAdminData(await api<AdminData>('/admin/overview')); setLoadError(''); return next; }
  useEffect(() => { let active = true; void refresh().catch(e => { if (active) setLoadError(errorText(e)); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [user.id]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 5500); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => { if (chatLog.current) chatLog.current.scrollTop = chatLog.current.scrollHeight; }, [visibleMessages.length, chatSurvey]);
  useEffect(() => {
    if (user.role !== 'customer') return;
    const markActivity = () => { setChatActivity(current => current + 1); };
    window.addEventListener('pointerdown', markActivity);
    window.addEventListener('keydown', markActivity);
    window.addEventListener('input', markActivity);
    return () => {
      window.removeEventListener('pointerdown', markActivity);
      window.removeEventListener('keydown', markActivity);
      window.removeEventListener('input', markActivity);
    };
  }, [user.role]);
  useEffect(() => {
    if (user.role !== 'customer' || !conversationActive || chatSurvey) return;
    return scheduleChatFeedback(() => {
      surveyPromptedAt.current = performance.now();
      surveySubmissionId.current = crypto.randomUUID();
      setSurveyScore(null);
      setChatSurvey(chooseChatSurvey());
    });
  }, [chatActivity, chatSurvey, conversationActive, user.role]);
  useEffect(() => { setMenu(false); setActionError(''); document.querySelector('main')?.focus(); }, [location.pathname, location.search]);
  const balance = data.products.reduce((total, p) => total + (p.balanceMinor || 0), 0);
  const productFilter = new URLSearchParams(location.search).get('product');
  const productKind = new URLSearchParams(location.search).get('kind');
  const visibleProducts = data.products.filter(p => productKind === 'cards' ? p.type === 'card' : productKind === 'accounts' ? p.type !== 'card' : true);
  const visibleTransactions = data.transactions.filter(tx => (!productFilter || tx.productId === productFilter) && (filter === 'all' || tx.status === filter) && (tx.merchant + ' ' + tx.id).toLowerCase().includes(search.toLowerCase()));
  const cases = user.role === 'admin' ? adminData.requests : data.requests;
  const events = user.role === 'admin' ? adminData.audit : data.audit;
  const currentCase = modal && 'id' in modal ? cases.find(r => r.id === modal.id) : undefined;
  function open(next: Modal) { setActionError(''); setModal(next); }
  async function changeLocale(value: Locale) { try { await api('/profile/locale', 'PATCH', { locale: value }); await i18n.changeLanguage(value); setUser({ ...user, locale: value }); } catch (e) { setActionError(errorText(e)); } }
  function focusChat() { document.querySelector('.assistant-panel')?.scrollIntoView({ block: 'center', behavior: 'smooth' }); chatInput.current?.focus({ preventScroll: true }); }
  function continueChat() {
    setChatSurvey(null);
    setSurveyScore(null);
    surveyPromptedAt.current = null;
    surveySubmissionId.current = null;
    setActionError('');
    setChatActivity(current => current + 1);
  }
  async function submitChatSurvey(event: FormEvent) {
    event.preventDefault();
    if (!chatSurvey || surveyScore === null || surveyBusy) return;
    const submissionId = surveySubmissionId.current ?? crypto.randomUUID();
    surveySubmissionId.current = submissionId;
    const formDurationMs = Math.max(0, Math.round(performance.now() - (surveyPromptedAt.current ?? performance.now())));
    const conversationDurationMs = Math.max(0, Math.round(performance.now() - (conversationStartedAt.current ?? performance.now())));
    setSurveyBusy(true);
    setActionError('');
    try {
      await api('/assistant/feedback', 'POST', {
        metric: chatSurvey,
        score: surveyScore,
        locale,
        submissionId,
        formDurationMs,
        conversationDurationMs,
      });
      setHiddenChatMessages(current => new Set([...current, ...data.messages.map(message => message.id)]));
      setChat('');
      setChatSurvey(null);
      setSurveyScore(null);
      setConversationActive(false);
      conversationStartedAt.current = null;
      surveyPromptedAt.current = null;
      surveySubmissionId.current = null;
      setChatActivity(current => current + 1);
      setNotice(t('surveyThanks'));
    } catch (error) {
      setActionError(errorText(error));
    } finally {
      setSurveyBusy(false);
    }
  }
  async function sendChat(message: string) {
    if (!message.trim() || chatBusy) return; setChatBusy(true); setActionError('');
    const startsNewConversation = !conversationActive;
    const startedAt = startsNewConversation ? performance.now() : null;
    try {
      const result = await api<{ destination: string | null; intent: string; text: string; navigation: NavigationCommand | null }>('/assistant', 'POST', { message: message.trim(), locale, currentPage: currentDestination(location.pathname, location.search) });
      if (startedAt !== null) conversationStartedAt.current = startedAt;
      setConversationActive(true);
      setChat('');
      await refresh();
      if (isRoutedIntent(result.intent)) {
        const destination = intentDestinations[result.intent];
        const navigated = await navigateForIntent(result.intent, navigate, error => setActionError(errorText(error)));
        if (navigated) setNotice(t('navigationDone', { screen: t(destination) }));
      } else if (result.destination === 'new-request') open({ type: 'create' });
      else {
        const route = safeNavigation(result.navigation);
        if (route) { navigate(route); setNotice(t('navigationDone', { screen: t(result.navigation!.destination) })); }
      }
    }
    catch (e) { setActionError(errorText(e)); } finally { setChatBusy(false); }
  }
  function readAnswer() {
    if (!('speechSynthesis' in window)) { setNotice(t('voiceUnavailable')); return; }
    const text = [...visibleMessages].reverse().find(m => m.role === 'assistant');
    const utterance = new SpeechSynthesisUtterance(text?.text || t('assistantIntro'));
    utterance.lang = text?.locale || locale;
    utterance.onerror = () => setNotice(t('voiceError'));
    speechSynthesis.cancel(); speechSynthesis.speak(utterance);
  }
  async function confirmAction() {
    if (!modal || !('id' in modal)) return; setBusy(true); setActionError('');
    try { await api(modal.type === 'review' ? '/admin/requests/' + modal.id + '/review' : '/requests/' + modal.id + '/handoff', 'POST', { confirmed: true }); await refresh(); setNotice(t(modal.type === 'review' ? 'reviewedToast' : 'handed')); setModal({ type: 'request', id: modal.id }); } catch (e) { setActionError(errorText(e)); } finally { setBusy(false); }
  }
  function caseCard(request: RequestCase) { return <button className="case-card" key={request.id} onClick={() => open({ type: 'request', id: request.id })}><div className="case-top"><span className="case-reference">{request.id}</span><Badge status={request.status} /></div><h3>{t(request.reason === 'amount' ? 'amountReason' : request.reason)}</h3><p>{request.customerName || t('requestHint')}</p><span className="text-link">{t('viewRequest')}<ArrowRight size={16} /></span></button>; }
  const pageTitle = location.pathname === '/admin' ? t('admin') : t(currentDestination(location.pathname, location.search));
  function auditLabel(action: string) { return action.startsWith('navigate_') ? t('navigationRecorded', { screen: t(action.slice(9)) }) : t(action === 'handed_off' ? 'handoffEvent' : action === 'logout' ? 'logoutEvent' : action); }
  return <div className={'app-shell ' + (large ? 'large-text' : '')}>
    <a className="skip-link" href="#main">{t('skip')}</a>
    <aside className={'sidebar ' + (menu ? 'mobile-open' : '')}><button className="icon-button menu-close" aria-label={t('close')} onClick={() => setMenu(false)}><X size={22} /></button><NavLink className="brand-link" to={user.role === 'admin' ? '/admin' : '/'} aria-label="Nexqori"><Brand /></NavLink><p className="brand-tagline">{t('tagline')}</p><p className="nav-label">{t('workspace')}</p><nav aria-label={t('workspace')}>{(user.role === 'admin' ? [{ path: '/admin', label: 'admin', Icon: ShieldCheck }] : navigation).map(({ path, label, Icon }) => <NavLink key={path} to={path} end className={({ isActive }) => 'nav-link ' + (isActive ? 'active' : '')}><Icon size={20} /><span>{t(label)}</span>{label === 'requests' && data.requests.length > 0 && <span className="nav-count">{data.requests.length}</span>}</NavLink>)}</nav>
    <div className="sidebar-bottom"><p className="nav-label">{t('support')}</p><NavLink to="/help" className="nav-link"><CircleHelp size={20} />{t('help')}</NavLink><button className="nav-link logout" onClick={() => { void signOut().catch(e => setActionError(errorText(e))); }}><LogOut size={19} />{t('logout')}</button>{user.role === 'customer' && <button className="sidebar-help" onClick={() => { setMenu(false); focusChat(); }}><span className="round-icon small"><Headphones size={21} /></span><strong>{t('assistantHint')}</strong><span>{t('focusAssistant')} <ArrowUpRight size={15} /></span></button>}<p className="sidebar-version">nexqori · v0.1</p></div></aside>
    {menu && <button className="menu-backdrop" aria-label={t('close')} onClick={() => setMenu(false)} />}<div className="workspace"><header className="topbar"><div className="topbar-left"><button className="icon-button menu-toggle" onClick={() => setMenu(!menu)} aria-label={t('menu')} aria-expanded={menu}><Menu size={22} /></button><span className="breadcrumb">nexqori <span>/</span> <strong>{pageTitle}</strong></span></div><div className="topbar-actions"><LanguagePicker onChange={value => { void changeLocale(value); }} /><button className={'icon-button text-size ' + (large ? 'selected' : '')} onClick={() => setLarge(!large)} aria-label={t('expandText')} aria-pressed={large}><Type size={19} /></button>{user.role === 'customer' && <button className="icon-button" aria-label={t('notifications')} onClick={() => navigate('/requests')}><Bell size={19} /></button>}<span className="avatar" title={user.name}>{user.name.split(' ').map(n => n[0]).slice(0, 2).join('')}</span></div></header>
    <div className={'workspace-body ' + (user.role === 'admin' ? 'admin-layout' : '')}><main id="main" tabIndex={-1}>
      {actionError && !modal && <p className="error-banner" role="alert">{actionError}</p>}
      {loading ? <div className="loading-panel" role="status"><RefreshCw className="spin" />{t('loading')}</div> : loadError ? <div className="empty-panel"><p role="alert">{loadError}</p><button className="button secondary" onClick={() => { setLoading(true); void refresh().catch(e => setLoadError(errorText(e))).finally(() => setLoading(false)); }}>{t('retry')}</button></div> :
      <Routes>
        <Route path="/" element={user.role === 'admin' ? <Navigate to="/admin" replace /> : <><div className="greeting"><p className="eyebrow">{t('greeting', { name: user.name.split(' ')[0] })} <span aria-hidden="true">✳</span></p><h1>{t('welcome')}</h1><p>{t('overview')}</p></div>
          <section className="balance-card"><div className="balance-decoration" aria-hidden="true" /><div className="balance-heading"><span>{t('balance')}</span><button className="icon-button on-dark" aria-label={t(hidden ? 'showBalance' : 'hideBalance')} onClick={() => setHidden(!hidden)}>{hidden ? <EyeOff size={19} /> : <Eye size={19} />}</button></div><div className="balance-number">{hidden ? '••••••' : formatMoney(balance, locale)}</div><p>{t('accountsTotal')}</p><div className="balance-footer"><button className="button light-button" onClick={() => navigate('/movements')}>{t('seeMovements')}<ArrowUpRight size={17} /></button><span className="balance-brand" aria-hidden="true">n.</span></div></section>
          <section className="quick-section"><div className="section-heading"><div><h2>{t('shortcutTitle')}</h2><p>{t('shortcutSubtitle')}</p></div></div><div className="quick-actions">{[{ key: 'askBalance', hint: 'balanceHint', Icon: Wallet, click: () => navigate('/products') }, { key: 'report', hint: 'reportHint', Icon: Search, click: () => open({ type: 'create' }) }, { key: 'track', hint: 'trackHint', Icon: FileText, click: () => navigate('/requests') }].map(({ key, hint, Icon, click }) => <button key={key} className="quick-action" onClick={click}><span className="quick-icon"><Icon size={21} /></span><strong>{t(key)}</strong><small>{t(hint)}</small><ArrowUpRight className="quick-arrow" size={16} /></button>)}</div></section>
          <section className="panel"><div className="section-heading"><h2>{t('recent')}</h2><button className="text-link" onClick={() => navigate('/movements')}>{t('seeAll')}<ArrowRight size={16} /></button></div>{data.transactions.length ? <TransactionList compact rows={data.transactions.slice(0, 4)} onSelect={transaction => open({ type: 'transaction', transaction })} /> : <p className="empty-copy">{t('noResults')}</p>}</section>
          {data.requests.length > 0 && <section className="progress-summary"><span className="round-icon small"><FileText size={20} /></span><div><h3>{t('myRequests')}</h3><p>{data.requests[0].id} · {t(data.requests[0].status)}</p></div><button className="icon-button" aria-label={t('viewRequest')} onClick={() => open({ type: 'request', id: data.requests[0].id })}><ArrowRight size={21} /></button></section>}
        </>} />
        <Route path="/movements" element={<><PageHeading title={t('movements')} subtitle={t('activityNote')} /><div className="filters"><label className="search-field"><Search size={19} /><span className="sr-only">{t('search')}</span><input type="search" placeholder={t('search')} value={search} onChange={e => setSearch(e.target.value)} /></label><label><span className="sr-only">{t('status')}</span><select value={filter} onChange={e => setFilter(e.target.value)} aria-label={t('status')}>{['all', 'completed', 'pending', 'declined'].map(status => <option key={status} value={status}>{t(status)}</option>)}</select></label></div><section className="panel transaction-panel"><TransactionList rows={visibleTransactions} onSelect={transaction => open({ type: 'transaction', transaction })} />{!visibleTransactions.length && <div className="empty-panel"><Search size={30} /><p>{t('noResults')}</p><button className="button secondary" onClick={() => { setSearch(''); setFilter('all'); navigate('/movements'); }}>{t('clear')}</button></div>}</section></>} />
        <Route path="/products" element={<><PageHeading title={t(productKind === 'accounts' || productKind === 'cards' ? productKind : 'products')} subtitle={t('productHint')} /><div className="product-grid">{visibleProducts.map(p => <article className={'product-card product-kind-' + p.type} key={p.id}><div className="section-heading"><span className="round-icon small">{p.type === 'card' ? <CreditCard size={22} /> : <Wallet size={22} />}</span><Badge status="active" /></div><h2>{t(p.type)}</h2><p className="muted">{t('ending')} •••• {p.last4}</p><strong className="product-amount">{p.balanceMinor === null ? '•••• •••• •••• ' + p.last4 : hidden ? '••••••' : formatMoney(p.balanceMinor, locale)}</strong><button className="text-link" onClick={() => { setSearch(''); setFilter('all'); navigate('/movements?product=' + encodeURIComponent(p.id)); }}>{t('seeMovements')}<ArrowRight size={17} /></button></article>)}</div>{!visibleProducts.length && <p className="empty-panel">{t('noProducts')}</p>}</>} />
        <Route path="/services" element={<><PageHeading title={t('services')} subtitle={t('serviceIntro')} /><p className="info-banner"><ShieldCheck size={20} />{t('serviceNote')}</p><div className="service-grid">{serviceItems.map(({ id, Icon }) => <article className="service-card" key={id}><span className="round-icon"><Icon size={23} /></span><h2>{t(id)}</h2><p>{t(id + 'Hint')}</p><button className="text-link" onClick={() => navigate(destinations[id])}>{t('consult')}<ArrowUpRight size={17} /></button></article>)}</div></>} />
        {serviceItems.filter(item => item.id !== 'accounts' && item.id !== 'cards').map(({ id, Icon }) => <Route key={id} path={'/services/' + id} element={<><PageHeading title={t(id)} subtitle={t(id + 'Hint')} /><section className="panel service-detail"><span className="round-icon"><Icon size={25} /></span><h2>{t('serviceNextStep')}</h2><p className="muted">{t('serviceDetail')}</p><div className="service-actions"><button className="button primary" onClick={() => open({ type: 'create', service: id })}><Plus size={18} />{t('newRequest')}</button><button className="button secondary" onClick={() => navigate('/movements')}>{t('seeMovements')}<ArrowRight size={17} /></button></div></section><p className="info-banner"><ShieldCheck size={20} />{t('serviceNote')}</p><button className="text-link" onClick={() => navigate('/services')}>{t('allServices')}<ArrowRight size={17} /></button></>} />)}
        <Route path="/requests" element={<><PageHeading title={t('requests')} subtitle={t('requestHint')} /><button className="button primary new-request" onClick={() => open({ type: 'create' })}><Plus size={18} />{t('newRequest')}</button><div className="requests-grid">{data.requests.map(caseCard)}</div>{!data.requests.length && <div className="empty-panel"><FileText size={32} /><h2>{t('noRequests')}</h2><p>{t('createFirst')}</p></div>}</>} />
        <Route path="/help" element={<><PageHeading title={t('helpTitle')} subtitle={t('helpBody')} /><div className="help-list">{[1, 2, 3].map(n => <details key={n}><summary>{t('help' + n)}<ChevronDown size={18} /></summary><p>{t('answer' + n)}</p></details>)}</div>{user.role === 'customer' && <button className="button primary" onClick={focusChat}><MessageCircle size={19} />{t('focusAssistant')}</button>}</>} />
        <Route path="/admin" element={user.role !== 'admin' ? <Navigate to="/" replace /> : <>
          <PageHeading title={t('adminTitle')} subtitle={t('adminNote')} />
          <FeedbackMetrics metrics={adminData.chatFeedback} />
          <div className="requests-grid">{adminData.requests.map(caseCard)}</div>
          <section className="panel admin-users"><h2>{t('users')}</h2><div className="table-scroll"><table><thead><tr><th>{t('customer')}</th><th>{t('email')}</th><th>{t('status')}</th><th>{t('language')}</th></tr></thead><tbody>{adminData.users.map(u => <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{t(u.role === 'admin' ? 'agent' : 'customer')}</td><td>{languageLabels[u.locale]}</td></tr>)}</tbody></table></div></section>
          <section className="panel"><h2>{t('audit')}</h2><ul className="audit-list">{adminData.audit.slice(0, 30).map(event => <li key={event.id}><span><strong>{auditLabel(event.action)}</strong><small>{event.actorName} · {event.requestId || '—'}</small></span><time>{formatDate(event.at, locale)}</time></li>)}</ul></section>
        </>} />
        <Route path="*" element={<Navigate to={user.role === 'admin' ? '/admin' : '/'} replace />} />
      </Routes>}
      <footer className="main-footer"><ShieldCheck size={14} />{t('footerNote')}<span>ES / EN / PT</span></footer>
    </main>
    {user.role === 'customer' && <aside className="assistant-panel" aria-label={t('assistant')}><div className="assistant-header"><span className="assistant-symbol"><Sparkles size={20} /></span><div><h2>{t('assistant')}</h2><p>{t('guided')}</p></div><button className="icon-button" onClick={readAnswer} aria-label={t('readAnswers')}><Volume2 size={19} /></button></div>
      <div ref={chatLog} className="chat-messages" tabIndex={0} aria-label={t('conversation')} role="log" aria-live="polite" aria-relevant="additions">
        <div className="assistant-welcome"><div className="nexqori-flower" aria-hidden="true">✳</div><h3>{t('assistantHello')}</h3><p>{t('assistantIntro')}</p></div>
        {!visibleMessages.length && <div className="chat-suggestions"><p className="eyebrow">{t('suggestions')}</p>{['askSaldo', 'askNavigate', 'askUnknown', 'askTrack'].map(key => <button key={key} disabled={chatBusy} onClick={() => { void sendChat(t(key)); }}>{t(key)}<ArrowUpRight size={15} /></button>)}</div>}
        {visibleMessages.map(message => <div className={'chat-bubble ' + message.role} key={message.id} lang={message.locale}>{message.text}</div>)}
        {chatSurvey && <ChatSurveyForm metric={chatSurvey} score={surveyScore} setScore={setSurveyScore} busy={surveyBusy} onSubmit={event => { void submitChatSurvey(event); }} onContinue={continueChat} />}
        {chatBusy && <p className="chat-thinking" role="status">{t('loading')}</p>}
      </div>
      <div className="chat-bottom"><form className="chat-composer" onSubmit={e => { e.preventDefault(); void sendChat(chat); }}><input ref={chatInput} aria-label={t('chatLabel')} placeholder={t('chatPlaceholder')} value={chat} onChange={e => setChat(e.target.value)} maxLength={1000} disabled={chatBusy} /><button type="submit" disabled={!chat.trim() || chatBusy} aria-label={t('send')}><Send size={18} /></button></form><button className="human-link" onClick={() => { void sendChat(t('talkHuman')); }} disabled={chatBusy}><Headphones size={15} />{t('talkHuman')}</button></div></aside>}
    </div></div>
    {notice && <div className="toast" role="status"><Check size={18} />{notice}</div>}
    {modal?.type === 'create' && <CreateRequest key={modal.transactionId || modal.service || 'new'} modal={modal} data={data} close={() => setModal(null)} saved={async (id, duplicate) => { await refresh(); setNotice(t(duplicate ? 'duplicate' : 'saved')); navigate('/requests'); open({ type: 'request', id }); }} />}
    {modal?.type === 'transaction' && <Dialog title={t('movementTitle')} onClose={() => setModal(null)}><div className="transaction-detail"><h3>{modal.transaction.merchant}</h3><strong>{formatMoney(modal.transaction.amountMinor, locale)}</strong><Badge status={modal.transaction.status} /></div><dl className="detail-list"><div><dt>{t('reference')}</dt><dd>{modal.transaction.id}</dd></div><div><dt>{t('date')}</dt><dd>{formatDate(modal.transaction.date, locale)}</dd></div><div><dt>{t('product')}</dt><dd>•••• {data.products.find(p => p.id === modal.transaction.productId)?.last4}</dd></div></dl><p className="info-banner">{t(modal.transaction.status === 'pending' ? 'pendingNote' : modal.transaction.status === 'declined' ? 'declinedNote' : 'noRefund')}</p><button className="button primary wide" onClick={() => open({ type: 'create', transactionId: modal.transaction.id })}>{t('createAbout')}<ArrowRight size={17} /></button></Dialog>}
    {modal?.type === 'request' && currentCase && <Dialog title={t('requestTitle')} onClose={() => setModal(null)}><div className="case-top"><strong>{currentCase.id}</strong><Badge status={currentCase.status} /></div><h3>{t(currentCase.reason === 'amount' ? 'amountReason' : currentCase.reason)}</h3><p className="case-details">{currentCase.details}</p><ol className="timeline">{events.filter(event => event.requestId === currentCase.id).slice().reverse().map(event => <li key={event.id}><span className="timeline-dot"><Check size={12} /></span><div><strong>{t(event.action === 'handed_off' ? 'handoffEvent' : event.action)}</strong><p>{formatDate(event.at, locale)} · {event.actorName}</p></div></li>)}</ol>{currentCase.status === 'handed_off' && <p className="info-banner">{t('noHuman')}</p>}{user.role === 'customer' && currentCase.status !== 'handed_off' && <button className="button secondary wide" onClick={() => open({ type: 'handoff', id: currentCase.id })}><Headphones size={18} />{t('handoff')}</button>}{user.role === 'admin' && currentCase.status === 'received' && <button className="button primary wide" onClick={() => open({ type: 'review', id: currentCase.id })}>{t('startReview')}</button>}</Dialog>}
    {(modal?.type === 'handoff' || modal?.type === 'review') && <Dialog title={t(modal.type === 'review' ? 'startReview' : 'handoff')} onClose={() => setModal(null)} busy={busy}><p>{modal.type === 'handoff' ? t('handoffExplain') : currentCase?.id}</p>{actionError && <p className="error-text" role="alert">{actionError}</p>}<div className="dialog-actions"><button className="button secondary" onClick={() => setModal(null)} disabled={busy}>{t('cancel')}</button><button className="button primary" disabled={busy} onClick={() => { void confirmAction(); }}>{busy ? t('loading') : t(modal.type === 'review' ? 'startReview' : 'confirmHandoff')}</button></div></Dialog>}
  </div>;
}
function PageHeading({ title, subtitle }: { title: string; subtitle: string }) { return <div className="page-heading"><h1>{title}</h1><p>{subtitle}</p></div>; }

function ChatSurveyForm({ metric, score, setScore, busy, onSubmit, onContinue }: { metric: ChatSurveyMetric; score: number | null; setScore: (score: number) => void; busy: boolean; onSubmit: (event: FormEvent) => void; onContinue: () => void }) {
  const { t } = useTranslation();
  const questionKey = metric === 'nps' ? 'surveyNpsQuestion' : metric === 'csat' ? 'surveyCsatQuestion' : 'surveyCesQuestion';
  const scaleDescription = ['surveyCsat1', 'surveyCsat2', 'surveyCsat3', 'surveyCsat4', 'surveyCsat5'];
  return <form className="chat-survey" onSubmit={onSubmit}>
    <p className="survey-eyebrow">{t('surveyIntro')}</p>
    <fieldset disabled={busy}>
      <legend>{t(questionKey)}</legend>
      <div className={'survey-scale survey-scale-' + metric} role="radiogroup">
        {chatSurveyScores(metric).map(value => <label className={'survey-score ' + (score === value ? 'selected' : '')} key={value}>
          <input type="radio" name={'chat-survey-' + metric} value={value} checked={score === value} onChange={() => setScore(value)} />
          <span aria-hidden="true">{metric === 'csat' ? ['😡', '😕', '😐', '🙂', '😄'][value - 1] : value}</span>
          <small>{metric === 'csat' ? t(scaleDescription[value - 1]) : value}</small>
        </label>)}
      </div>
      {metric !== 'csat' && <div className="survey-endpoints"><span>{t(metric === 'nps' ? 'surveyNpsLow' : 'surveyCesLow')}</span><span>{t(metric === 'nps' ? 'surveyNpsHigh' : 'surveyCesHigh')}</span></div>}
    </fieldset>
    <div className="survey-actions">
      <button type="submit" className="button primary" disabled={score === null || busy}>{busy ? t('loading') : t('submitSurvey')}</button>
      <button type="button" className="text-link" disabled={busy} onClick={onContinue}>{t('continueChat')}</button>
    </div>
  </form>;
}

function FeedbackMetrics({ metrics }: { metrics: AdminData['chatFeedback'] }) {
  const { t } = useTranslation();
  const cards = (['nps', 'csat', 'ces'] as const).map(metric => {
    const result = metrics[metric];
    return {
      metric,
      result,
      value: metric === 'nps' ? result.npsScore === null ? '—' : formatNumber(result.npsScore, 1) : metric === 'csat' ? result.csatPercent === null ? '—' : formatNumber(result.csatPercent, 1) + '%' : result.averageScore === null ? '—' : formatNumber(result.averageScore, 2),
      label: metric === 'nps' ? 'npsLabel' : metric === 'csat' ? 'csatLabel' : 'cesLabel',
      formula: metric === 'nps' ? 'npsResult' : metric === 'csat' ? 'csatResult' : 'cesResult',
    };
  });
  return <section className="feedback-dashboard" aria-labelledby="feedback-dashboard-title">
    <div className="section-heading"><div><h2 id="feedback-dashboard-title">{t('surveyMetricsTitle')}</h2><p>{t('surveyMetricsNote')}</p></div></div>
    <div className="feedback-metrics">{cards.map(({ metric, result, value, label, formula }) => <article className="feedback-metric panel" key={metric}>
      <div className="feedback-metric-heading"><h3>{t(label)}</h3><span>{t('surveyResponses', { count: result.responses })}</span></div>
      <strong className="feedback-value">{value}</strong>
      <p>{t(formula)}</p>
      <dl><div><dt>{t('surveyAverageScore')}</dt><dd>{result.averageScore === null ? '—' : formatNumber(result.averageScore)}</dd></div><div><dt>{t('averageFormTime')}</dt><dd>{formatDuration(result.averageFormDurationMs)}</dd></div><div><dt>{t('averageConversationTime')}</dt><dd>{formatDuration(result.averageConversationDurationMs)}</dd></div></dl>
    </article>)}</div>
  </section>;
}

function Root() {
  const [user, setUser] = useState<User | null>(null); const [ready, setReady] = useState(false); const [bootError, setBootError] = useState(''); const navigate = useNavigate(); const { t } = useTranslation();
  useEffect(() => { const end = () => { setUser(null); setCsrf(''); }; window.addEventListener('nexqori-session-ended', end); void api<{ user: User; csrfToken: string }>('/session').then(result => { setCsrf(result.csrfToken); setUser(result.user); void i18n.changeLanguage(result.user.locale); }).catch(error => { if (!(error instanceof ApiError && error.status === 401)) setBootError(errorText(error)); }).finally(() => setReady(true)); return () => window.removeEventListener('nexqori-session-ended', end); }, []);
  async function signOut() { await api('/auth/logout', 'POST', {}); if ('speechSynthesis' in window) speechSynthesis.cancel(); setCsrf(''); setUser(null); navigate('/', { replace: true }); }
  if (!ready) return <div className="loading-screen"><Brand /><p role="status">{t('loading')}</p></div>;
  if (!user) return <>{bootError && <div className="error-banner" role="alert">{bootError}</div>}<Login onLogin={next => { setUser(next); setBootError(''); navigate(next.role === 'admin' ? '/admin' : '/', { replace: true }); }} /></>;
  return <Shell user={user} setUser={setUser} signOut={signOut} />;
}
export default function App() { return <BrowserRouter><Root /></BrowserRouter>; }
