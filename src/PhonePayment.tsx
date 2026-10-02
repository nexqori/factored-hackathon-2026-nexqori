import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Smartphone, ArrowRight } from 'lucide-react';
import { api, ApiError } from './api';
import { formatMoney } from './components';
import type { Dashboard } from './types';
import { localeTags, type Locale } from './i18n';
import './bank-flow.css';

type Bill = { id: string; reference: string; provider: string; period: string; dueDate: string; amountMinor: number; currency: string; paymentId: string | null };
type Receipt = { id: string; transactionId: string; provider: string; reference: string; period: string; amountMinor: number; currency: string; accountLast4: string; date: string; status: string };
const failure = (e: unknown) => 'error.' + (e instanceof ApiError ? e.code : 'generic');

export function PaymentReceipt({ paymentId, compact = false }: { paymentId?: string; compact?: boolean }) {
  const params = useParams(); const id = paymentId || params.paymentId;
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [receipt, setReceipt] = useState<Receipt | null>(null); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { const c = new AbortController(); setError(''); setReceipt(null); void api<Receipt>('/payments/' + encodeURIComponent(id || ''), 'GET', undefined, c.signal).then(setReceipt).catch(e => { if (!c.signal.aborted) setError(failure(e)); }); return () => c.abort(); }, [id, retry]);
  if (error) return <div role="alert"><p>{t(error)}</p><button className="button secondary" onClick={() => setRetry(v => v + 1)}>{t('retry')}</button></div>;
  if (!receipt) return <p role="status">{t('loading')}</p>;
  return <section className={compact ? 'payment-receipt compact' : 'panel payment-receipt'} data-payment-id={receipt.id}>
    {!compact && <><span className="payment-check"><CheckCircle2 size={44}/></span><h1>{t('pay.done')}</h1><p>{t('pay.doneHint')}</p><strong className="payment-amount">{formatMoney(receipt.amountMinor, locale, receipt.currency)}</strong></>}
    <dl className="detail-list"><div><dt>{t('operationId')}</dt><dd><code>{receipt.id}</code></dd></div><div><dt>{t('catalogProvider')}</dt><dd>{receipt.provider}</dd></div><div><dt>{t('catalogReference_phone')}</dt><dd>{receipt.reference}</dd></div><div><dt>{t('pay.period')}</dt><dd>{receipt.period}</dd></div><div><dt>{t('catalogSourceAccount')}</dt><dd>•••• {receipt.accountLast4}</dd></div><div><dt>{t('date')}</dt><dd>{new Intl.DateTimeFormat(localeTags[locale], { dateStyle:'medium', timeStyle:'short' }).format(new Date(receipt.date))}</dd></div><div><dt>{t('linkedMovement')}</dt><dd><code>{receipt.transactionId}</code></dd></div></dl>
    {!compact && <Link className="button primary" to="/movements">{t('seeMovements')}<ArrowRight size={18}/></Link>}
  </section>;
}

export function PhonePayment({ data, saved }: { data: Dashboard; saved: (id: string) => Promise<void> }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale; const navigate = useNavigate();
  const [bills, setBills] = useState<Bill[] | null>(null); const [billId, setBillId] = useState(''); const [accountId, setAccountId] = useState(data.products.find(p => p.type === 'account')?.id || '');
  const [review, setReview] = useState(false); const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const busyRef = useRef(false);
  const [error, setError] = useState(''); const [retry, setRetry] = useState(0); const [key, setKey] = useState(() => crypto.randomUUID());
  useEffect(() => { const c = new AbortController(); setError(''); void api<{bills: Bill[]}>('/phone-bills', 'GET', undefined, c.signal).then(r => { if (!c.signal.aborted) { setBills(r.bills); setBillId(r.bills.find(b => !b.paymentId)?.id || r.bills[0]?.id || ''); } }).catch(e => { if (!c.signal.aborted) setError(failure(e)); }); return () => c.abort(); }, [retry]);
  const bill = bills?.find(b => b.id === billId); const account = data.products.find(p => p.id === accountId);
  async function pay() {
    if (!bill || !confirmed || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    try {
      const receipt = await api<Receipt>('/phone-bills/' + bill.id + '/pay', 'POST', { accountId, confirmed: true, requestKey: key });
      // The receipt is authoritative even if refreshing the rest of the page fails.
      navigate('/payments/' + receipt.id); void saved(receipt.id).catch(() => {});
    } catch (e) { setError(failure(e)); } finally { busyRef.current = false; setBusy(false); }
  }
  return <div className="service-workspace"><div className="service-page-header"><span className="round-icon"><Smartphone size={28}/></span><div><p className="eyebrow">{bill?.provider || t('payments')}</p><h1>{t('pay.title')}</h1><p>{t('pay.intro')}</p></div></div>
    <section className="panel phone-bill"><h2>{t(review ? 'pay.review' : 'pay.bill')}</h2>
      {bills === null && !error && <p role="status">{t('loading')}</p>}
      {bills?.length === 0 && <p>{t('pay.empty')}</p>}
      {bill && <>
        {!review && bills!.length > 1 && <label>{t('pay.bill')}<select value={billId} onChange={e => { setBillId(e.target.value); setError(''); setKey(crypto.randomUUID()); }}>{bills!.map(b => <option key={b.id} value={b.id}>{b.reference} · {b.period} · {t(b.paymentId ? 'pay.paid' : 'pay.due')}</option>)}</select></label>}
        <div className="bill-total"><span>{t(bill.paymentId ? 'pay.paid' : 'pay.monthly')}</span><strong>{formatMoney(bill.amountMinor, locale, bill.currency)}</strong></div>
        <dl className="detail-list"><div><dt>{t('catalogReference_phone')}</dt><dd>{bill.reference}</dd></div><div><dt>{t('pay.period')}</dt><dd>{bill.period}</dd></div><div><dt>{t('pay.dueDate')}</dt><dd>{bill.dueDate}</dd></div></dl>
        {bill.paymentId ? <Link className="button primary" to={'/payments/' + bill.paymentId}>{t('pay.receipt')}<ArrowRight size={18}/></Link> : <>
          {!review ? <><label className="form-stack">{t('catalogSourceAccount')}<select value={accountId} onChange={e => { setAccountId(e.target.value); setKey(crypto.randomUUID()); }}><option value="">{t('catalogChooseAccount')}</option>{data.products.filter(p => p.type !== 'card' && p.currency === bill.currency).map(p => <option key={p.id} value={p.id}>{t(p.type)} · •••• {p.last4} · {formatMoney(p.balanceMinor || 0, locale)}</option>)}</select></label><button className="button primary" disabled={!account} onClick={() => { setReview(true); setConfirmed(false); setError(''); }}>{t('pay.review')}<ArrowRight size={18}/></button></> : <form className="form-stack" onSubmit={e => { e.preventDefault(); void pay(); }}>
            <p>{t('pay.debitFrom', { account: account?.last4 })}</p><label className="checkbox-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)}/>{t('pay.confirmCheck')}</label>
            <div className="service-form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setReview(false)}>{t('catalogEdit')}</button><button className="button primary" disabled={!confirmed || busy}>{t(busy ? 'loading' : 'pay.confirm')}</button></div>
          </form>}
        </>}
      </>}
      {error && <p className="error-text" role="alert">{t(error)}</p>}{error && bills === null && <button className="button secondary" onClick={() => setRetry(v => v + 1)}>{t('retry')}</button>}
    </section>
  </div>;
}
