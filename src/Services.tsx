import { useEffect, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, ArrowLeftRight, Search, X, Smartphone, Wifi, Tv, Lightbulb, Wallet, CreditCard, Activity, ShieldCheck, ReceiptText, House, ChartNoAxesCombined, Umbrella, Banknote, CircleHelp, MessageCircle, Check } from 'lucide-react';
import { api, ApiError } from './api';
import { Badge, formatMoney } from './components';
import { destinations, type Destination } from './navigation';
import { localService, parseAmount, serviceTitle } from './catalog';
import type { Locale } from './i18n';
import type { Dashboard, RequestCase, Service, ServiceItem } from './types';

const icons: Record<string, typeof Wallet> = { phone: Smartphone, wifi: Wifi, tv: Tv, utility: Lightbulb, wallet: Wallet, card: CreditCard, transfer: ArrowLeftRight, activity: Activity, shield: ShieldCheck, receipt: ReceiptText, home: House, loan: House, chart: ChartNoAxesCombined, umbrella: Umbrella, cash: Banknote, help: CircleHelp, message: MessageCircle };
const categories: Service[] = ['payments', 'transfers', 'accounts', 'cards', 'loans', 'investments', 'insurance', 'cash', 'support'];
const suggestionIds = ['phone-bill', 'internet-bill', 'bank-transfer', 'unrecognized-charge'];
const failure = (error: unknown) => 'error.' + (error instanceof ApiError ? error.code : 'generic');

export function ServiceIcon({ item }: { item: ServiceItem }) {
  const Icon = icons[item.icon] || CircleHelp;
  return <span className={'catalog-icon icon-' + item.icon}><Icon size={25} aria-hidden="true" /></span>;
}

export function ServiceDirectory() {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const { category } = useParams(); const navigate = useNavigate(); const location = useLocation();
  const [query, setQuery] = useState(() => new URLSearchParams(location.search).get('q') || '');
  const [items, setItems] = useState<ServiceItem[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { setQuery(new URLSearchParams(location.search).get('q') || ''); }, [location.search]);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    const timer = setTimeout(() => {
      const search = new URLSearchParams({ q: query, locale }); if (category) search.set('category', category);
      void api<{ items: ServiceItem[] }>('/services?' + search, 'GET', undefined, controller.signal)
        .then(result => { if (!controller.signal.aborted) setItems(result.items); })
        .catch(e => { if (!controller.signal.aborted) setError(failure(e)); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, category, locale, retry]);
  function selectCategory(value?: string) { navigate('/services' + (value ? '/' + value : '') + (query ? '?q=' + encodeURIComponent(query) : '')); }
  return <div className="service-directory">
    <div className="page-heading"><p className="eyebrow">{t('catalogEyebrow')}</p><h1>{t(category || 'services')}</h1><p>{t('catalogIntro')}</p></div>
    <section className="catalog-search-panel" aria-label={t('catalogSearchLabel')}>
      <div className="catalog-search-title"><span className="round-icon"><Search size={24} /></span><div><h2>{t('catalogQuestion')}</h2><p>{t('catalogSearchHint')}</p></div></div>
      <label className="catalog-search"><Search size={21} aria-hidden="true" /><span className="sr-only">{t('catalogSearchLabel')}</span><input type="search" maxLength={120} value={query} onChange={e => setQuery(e.target.value)} placeholder={t('catalogPlaceholder')} autoComplete="off" />{query && <button type="button" className="icon-button" aria-label={t('clear')} onClick={() => setQuery('')}><X size={18} /></button>}</label>
      <div className="catalog-suggestions"><span>{t('catalogTry')}</span>{suggestionIds.map(id => <button key={id} onClick={() => { setQuery(serviceTitle(id, locale)); if (category) navigate('/services?q=' + encodeURIComponent(serviceTitle(id, locale))); }}>{serviceTitle(id, locale)}</button>)}</div>
    </section>
    <nav className="catalog-categories" aria-label={t('catalogCategories')}><button aria-pressed={!category} onClick={() => selectCategory()}>{t('all')}</button>{categories.map(id => <button key={id} aria-pressed={category === id} onClick={() => selectCategory(id)}>{t(id === 'support' ? 'catalogSupport' : id)}</button>)}</nav>
    <div className="catalog-result-heading"><h2>{query ? t('catalogResults') : t('catalogExplore')}</h2><span role="status" aria-live="polite">{loading ? t('loading') : !error ? t('catalogCount', { count: items.length }) : ''}</span></div>
    {error ? <div className="empty-panel" role="alert"><p>{t(error)}</p><button className="button secondary" onClick={() => setRetry(retry + 1)}>{t('retry')}</button></div> : <div className="catalog-results" aria-busy={loading} data-catalog-ready={!loading}>
      {!loading && items.map(item => <Link className="catalog-card" data-service-id={item.id} key={item.id} to={item.kind === 'navigate' && item.target && Object.hasOwn(destinations, item.target) ? destinations[item.target as Destination] : '/services/catalog/' + item.id}>
        <ServiceIcon item={item} /><div className="catalog-card-copy"><small>{item.provider || t(item.category === 'support' ? 'catalogSupport' : item.category)}</small><h3>{item.title}</h3><p>{item.summary}</p><span className="text-link">{t(item.kind === 'navigate' ? 'consult' : 'catalogContinue')}<ArrowRight size={16} /></span></div>
      </Link>)}
      {!loading && !items.length && <div className="catalog-empty"><Search size={32} /><h3>{t('catalogNoResults')}</h3><p>{t('catalogNoResultsHint')}</p><button className="button secondary" onClick={() => { setQuery(''); navigate('/services'); }}>{t('allServices')}</button></div>}
    </div>}
  </div>;
}

export function ServiceRequestDetails({ request }: { request: RequestCase }) {
  const { t, i18n } = useTranslation(); const data = request.serviceData;
  if (!data) return null;
  const item = localService(request.catalogServiceId || '', i18n.language as Locale);
  return <dl className="detail-list service-receipt-details">
    {data.provider && <div><dt>{t('catalogProvider')}</dt><dd>{data.provider}</dd></div>}
    {data.reference && <div><dt>{t('catalogReference_' + (item?.referenceKind || 'receipt'))}</dt><dd>{data.reference}</dd></div>}
    {data.beneficiary && <div><dt>{t('catalogBeneficiary')}</dt><dd>{data.beneficiary}</dd></div>}
    {data.accountLast4 && <div><dt>{t('catalogSourceAccount')}</dt><dd>•••• {data.accountLast4}</dd></div>}
    {data.amountMinor !== null && <div><dt>{t('amount')}</dt><dd>{formatMoney(data.amountMinor, i18n.language as Locale, data.currency || 'MXN')}</dd></div>}
  </dl>;
}

export function ServicePage({ data, saved }: { data: Dashboard; saved: (id: string) => Promise<void> }) {
  const { serviceId = '' } = useParams(); const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [item, setItem] = useState<ServiceItem | null>(null); const [loadError, setLoadError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { const c = new AbortController(); setLoadError(''); setItem(previous => previous?.id === serviceId ? previous : null); void api<ServiceItem>('/services/' + encodeURIComponent(serviceId) + '?locale=' + locale, 'GET', undefined, c.signal).then(value => { if (!c.signal.aborted) setItem(value); }).catch(e => { if (!c.signal.aborted) setLoadError(failure(e)); }); return () => c.abort(); }, [serviceId, locale, retry]);
  if (loadError) return <div className="empty-panel"><p role="alert">{t(loadError)}</p><button className="button secondary" onClick={() => setRetry(retry + 1)}>{t('retry')}</button><Link className="text-link" to="/services">{t('allServices')}</Link></div>;
  if (!item) return <p role="status">{t('loading')}</p>;
  if (item.kind === 'navigate' && item.target && Object.hasOwn(destinations, item.target)) return <Link className="button primary" to={destinations[item.target as Destination]}>{item.title}<ArrowRight size={18} /></Link>;
  return <ServiceForm key={item.id} item={item} data={data} saved={saved} />;
}

function ServiceForm({ item, data, saved }: { item: ServiceItem; data: Dashboard; saved: (id: string) => Promise<void> }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const accounts = data.products.filter(p => p.type !== 'card' && p.currency === 'MXN');
  const monetary = item.kind === 'bill' || item.kind === 'transfer';
  const needsTransaction = item.workflow?.requiredFields.includes('transactionId') ?? ['unrecognized-charge', 'incorrect-charge', 'payment-status'].includes(item.id);
  const [accountId, setAccountId] = useState(accounts[0]?.id || ''); const [reference, setReference] = useState(''); const [beneficiary, setBeneficiary] = useState(''); const [amount, setAmount] = useState(''); const [notes, setNotes] = useState(''); const [transactionId, setTransactionId] = useState('');
  const [review, setReview] = useState(false); const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [requestKey, setRequestKey] = useState(() => crypto.randomUUID()); const [receipt, setReceipt] = useState<string | null>(null);
  const amountMinor = parseAmount(amount); const account = accounts.find(p => p.id === accountId);
  const referenceLabel = t('catalogReference_' + item.referenceKind);
  function prepare(e: FormEvent) {
    e.preventDefault(); setError('');
    if (monetary && (!account || amountMinor === null)) { setError('error.service_amount'); return; }
    if (monetary && (item.referenceKind === 'phone' ? !/^\+?[0-9 ()-]{6,24}$/.test(reference.trim()) || reference.replace(/\D/g, '').length < 6 || reference.replace(/\D/g, '').length > 15 : !/^[A-Za-z0-9][A-Za-z0-9 /.-]{2,63}$/.test(reference.trim()))) { setError('error.service_reference'); return; }
    if (!monetary && notes.trim().length < 10) { setError('error.details'); return; }
    setReview(true); setConfirmed(false);
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); if (busy) return; if (!confirmed) { setError('confirmationError'); return; }
    setBusy(true); setError('');
    try {
      const result = await api<{ id: string; duplicate: boolean }>('/services/' + item.id + '/requests', 'POST', { requestKey, locale, confirmed: true, accountId: monetary ? accountId : null, reference: monetary ? reference : '', beneficiary: item.kind === 'transfer' ? beneficiary : '', amountMinor: monetary ? amountMinor : null, transactionId: transactionId || null, notes });
      setReceipt(result.id); await saved(result.id);
    } catch (e) { setError(failure(e)); } finally { setBusy(false); }
  }
  return <div className="service-workspace">
    <Link className="text-link service-back" to={'/services/' + item.category}><ArrowLeft size={17} />{t('allServices')}</Link>
    <div className="service-page-header"><ServiceIcon item={item} /><div><p className="eyebrow">{item.provider || t(item.category === 'support' ? 'catalogSupport' : item.category)}</p><h1>{item.title}</h1><p>{item.summary}</p></div></div>
    <>{item.workflow && <details className="workflow-procedure" open><summary>{t('workflowSteps')}</summary><ol>{item.workflow.steps.map((step,index)=><li key={index}>{step}</li>)}</ol><p>{t('workflowOutcome')}</p></details>}</><ol className="service-steps" aria-label={t('catalogSteps')}>{['catalogStepDetails', 'catalogStepReview', 'catalogStepFollow'].map((key, index) => <li key={key} aria-current={(receipt ? 2 : review ? 1 : 0) === index ? 'step' : undefined}><span>{index + 1}</span>{t(key)}</li>)}</ol>
    <section className="panel service-operation">
      {receipt ? <div className="service-success"><span className="round-icon"><Check size={30} /></span><h2>{t('catalogReceived')}</h2><p>{t('catalogReceivedHint')}</p><strong className="case-reference">{receipt}</strong><Badge status="received" /><Link className="button primary" to="/requests">{t('requests')}<ArrowRight size={18} /></Link></div> : !review ? <form className="form-stack" onSubmit={prepare}>
        <h2>{t('catalogDetailsTitle')}</h2>
        {monetary && <>
          <label>{t('catalogSourceAccount')}<select required value={accountId} onChange={e => setAccountId(e.target.value)}><option value="">{t('catalogChooseAccount')}</option>{accounts.map(p => <option key={p.id} value={p.id}>{t(p.type)} · •••• {p.last4} · {formatMoney(p.balanceMinor || 0, locale)}</option>)}</select></label>
          {!accounts.length && <p className="info-banner">{t('catalogNoAccount')}</p>}
          <label>{referenceLabel}<input value={reference} onChange={e => setReference(e.target.value)} inputMode={item.referenceKind === 'phone' ? 'tel' : 'text'} autoComplete="off" required minLength={item.referenceKind === 'phone' ? 6 : 3} maxLength={item.referenceKind === 'phone' ? 24 : 64} aria-describedby="service-reference-help" /></label>
          <small className="muted" id="service-reference-help">{t(item.referenceKind === 'phone' ? 'catalogPhoneHint' : 'catalogReferenceHint')}</small>
          {item.kind === 'transfer' && <label>{t('catalogBeneficiary')}<input value={beneficiary} onChange={e => setBeneficiary(e.target.value)} minLength={3} maxLength={100} required autoComplete="off" /></label>}
          <label>{t('catalogAmount')}<div className="service-amount-input"><input value={amount} onChange={e => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00" maxLength={11} required pattern="[0-9]+([.,][0-9]{1,2})?" aria-describedby="service-amount-help" /><span>MXN</span></div></label><small className="muted" id="service-amount-help">{t('catalogAmountHint')}</small>
        </>}
        {item.kind === 'claim' && <label>{t('chooseTransaction')}<select required={needsTransaction} value={transactionId} onChange={e => setTransactionId(e.target.value)}><option value="">{t(needsTransaction ? 'catalogChooseMovement' : 'noTransaction')}</option>{data.transactions.map(tx => <option key={tx.id} value={tx.id}>{tx.merchant} · {formatMoney(tx.amountMinor, locale)} · {t(tx.status)}</option>)}</select></label>}
        <label>{t(monetary ? 'catalogNoteOptional' : 'detailLabel')}<textarea rows={3} value={notes} onChange={e => setNotes(e.target.value)} maxLength={1000} required={!monetary} minLength={monetary ? undefined : 10} placeholder={t('catalogNotePlaceholder')} /></label>
        {error && <p role="alert" className="error-text">{t(error)}</p>}
        <button className="button primary" disabled={monetary && !accounts.length}>{t('catalogReview')}<ArrowRight size={18} /></button>
      </form> : <form className="form-stack" onSubmit={submit}>
        <h2>{t('catalogReviewTitle')}</h2><p>{t('catalogReviewHint')}</p>
        <dl className="detail-list"><div><dt>{t('catalogService')}</dt><dd>{item.title}</dd></div>{item.provider && <div><dt>{t('catalogProvider')}</dt><dd>{item.provider}</dd></div>}{monetary && <><div><dt>{t('catalogSourceAccount')}</dt><dd>{t(account!.type)} · •••• {account!.last4}</dd></div><div><dt>{referenceLabel}</dt><dd>{reference}</dd></div>{beneficiary && <div><dt>{t('catalogBeneficiary')}</dt><dd>{beneficiary}</dd></div>}<div><dt>{t('amount')}</dt><dd className="service-review-amount">{formatMoney(amountMinor!, locale)}</dd></div></>}{transactionId && <div><dt>{t('reference')}</dt><dd>{transactionId}</dd></div>}{notes && <div><dt>{t('detailLabel')}</dt><dd>{notes}</dd></div>}</dl>
        <label className="checkbox-label"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />{t('catalogConfirmCheck')}</label>
        {error && <p role="alert" className="error-text">{t(error)}</p>}
        <div className="service-form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => { setReview(false); setError(''); setRequestKey(crypto.randomUUID()); }}>{t('catalogEdit')}</button><button className="button primary" disabled={busy}>{t(busy ? 'loading' : 'catalogConfirm')}<ArrowRight size={18} /></button></div>
      </form>}
    </section>
  </div>;
}
