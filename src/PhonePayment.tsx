import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CheckCircle2, Clock3, ArrowRight } from 'lucide-react';
import { api, ApiError } from './api';
import { formatMoney } from './components';
import { localeTags, type Locale } from './i18n';
import './bank-flow.css';

type Receipt = { serviceId?: string; remainingMinor?: number; id: string; transactionId: string; provider: string; reference: string; period: string; amountMinor: number; currency: string; accountLast4: string; date: string; status: string };
const failure = (e: unknown) => 'error.' + (e instanceof ApiError ? e.code : 'generic');

export function PaymentReceipt({ paymentId, compact = false }: { paymentId?: string; compact?: boolean }) {
  const params = useParams(); const id = paymentId || params.paymentId;
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [receipt, setReceipt] = useState<Receipt | null>(null); const [error, setError] = useState(''); const [retry, setRetry] = useState(0);
  useEffect(() => { const c = new AbortController(); setError(''); setReceipt(null); void api<Receipt>('/payments/' + encodeURIComponent(id || ''), 'GET', undefined, c.signal).then(setReceipt).catch(e => { if (!c.signal.aborted) setError(failure(e)); }); return () => c.abort(); }, [id, retry]);
  if (error) return <div role="alert"><p>{t(error)}</p><button className="button secondary" onClick={() => setRetry(v => v + 1)}>{t('retry')}</button></div>;
  if (!receipt) return <p role="status">{t('loading')}</p>;
  const pending=receipt.status==='pending';
  return <section className={compact ? 'payment-receipt compact' : 'panel payment-receipt'} data-payment-id={receipt.id} data-payment-status={receipt.status}>
    {!compact && <><span className={'payment-check'+(pending?' payment-pending':'')}>{pending?<Clock3 size={44} aria-hidden="true"/>:<CheckCircle2 size={44} aria-hidden="true"/>}</span><h1>{t(pending?'pay.pendingTitle':'pay.done')}</h1><p>{t(pending?'pay.pendingHint':'pay.doneHint')}</p><strong className="payment-amount">{formatMoney(receipt.amountMinor, locale, receipt.currency)}</strong></>}
    {compact&&pending&&<p className="bill-pending-note">{t('pay.pendingHint')}</p>}
    <dl className="detail-list"><div><dt>{t('operationId')}</dt><dd><code>{receipt.id}</code></dd></div><div><dt>{t('catalogProvider')}</dt><dd>{receipt.provider}</dd></div><div><dt>{t('bills.reference')}</dt><dd>{receipt.reference}</dd></div><div><dt>{t('pay.period')}</dt><dd>{receipt.period}</dd></div><div><dt>{t('catalogSourceAccount')}</dt><dd>•••• {receipt.accountLast4}</dd></div><div><dt>{t('date')}</dt><dd>{new Intl.DateTimeFormat(localeTags[locale], { dateStyle:'medium', timeStyle:'short',timeZone:'America/Mexico_City' }).format(new Date(receipt.date))}</dd></div><div><dt>{t('linkedMovement')}</dt><dd><code>{receipt.transactionId}</code></dd></div></dl>
    {!pending&&receipt.remainingMinor != null && receipt.remainingMinor > 0 && <p>{t('bills.after',{amount:formatMoney(receipt.remainingMinor,locale,receipt.currency)})}</p>}
    {!compact && <Link className="button primary" to="/movements">{t('seeMovements')}<ArrowRight size={18}/></Link>}
    {!compact && <Link className="button secondary" to={'/services/catalog/'+(receipt.serviceId||'phone-bill')}>{t('bills.another')}</Link>}
  </section>;
}
