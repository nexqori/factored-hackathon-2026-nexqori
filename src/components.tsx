import { productLabelKey } from './productLabels';
import { useEffect, useId, useRef, type ReactNode } from 'react';
import { X, ArrowUpRight, ShoppingBag, Coffee, ArrowDownLeft, Zap, Play, CircleHelp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { localeTags, type Locale } from './i18n';
import type { Transaction, Product } from './types';
export const formatMoney = (minor: number, locale: Locale, currency = 'MXN') => new Intl.NumberFormat(localeTags[locale], { style: 'currency', currency, currencyDisplay: 'code' }).format(minor / 100);
export const formatDate = (date: string, locale: Locale) => new Intl.DateTimeFormat(localeTags[locale], { day: 'numeric', month: 'short', timeZone: 'America/Mexico_City' }).format(new Date(date));
export function Brand({ light = false }: { light?: boolean }) { return <span className={'brand ' + (light ? 'light' : '')}><img src="/nexqori.svg" width="38" height="38" alt="" /><span>nexqori<span className="brand-dot">.</span></span></span>; }
export function Badge({ status }: { status: string }) { const { t } = useTranslation(); return <span className={'badge status-' + status}><span aria-hidden="true" />{t(status)}</span>; }
export function TransactionIcon({ category }: { category: string }) {
  const Icon = ({ shopping: ShoppingBag, food: Coffee, transfer: ArrowDownLeft, utilities: Zap, subscription: Play } as Record<string, typeof ShoppingBag>)[category] || CircleHelp;
  return <span className={'transaction-icon category-' + category}><Icon size={19} aria-hidden="true" /></span>;
}
export function TransactionList({ rows, onSelect, compact = false, products, highlightedId }: { highlightedId?:string|null; rows: Transaction[]; onSelect: (tx: Transaction) => void; compact?: boolean; products?: Product[] }) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  return <div className={'transaction-list ' + (compact ? 'compact' : '') + (products ? ' movement-details' : '')}>{rows.map(tx => <button className={'transaction-row'+(highlightedId===tx.id?' movement-highlighted':'')} data-transaction-id={tx.id} key={tx.id} onClick={() => onSelect(tx)}>
    <TransactionIcon category={tx.category} /><span className="transaction-name"><strong>{tx.merchant}</strong><small>{t(tx.category)} · {formatDate(tx.date, locale)}</small></span>
    {products && <span className="movement-meta"><span>{t('product')}: {(() => { const product = products.find(p => p.id === tx.productId); return product ? t(productLabelKey(product)) + ' · •••• ' + product.last4 : tx.productId; })()}</span><time dateTime={tx.date}>{new Intl.DateTimeFormat(localeTags[locale], {dateStyle:'medium', timeStyle:'short', timeZone:'America/Mexico_City'}).format(new Date(tx.date))}</time></span>}
    {!compact && <Badge status={tx.status} />}<span className={'transaction-amount ' + (tx.amountMinor > 0 ? 'positive' : '')}>{tx.amountMinor > 0 ? '+' : ''}{formatMoney(tx.amountMinor, locale, tx.currency)}{compact && tx.status !== 'completed' && <small>{t(tx.status)}</small>}</span><ArrowUpRight size={16} aria-hidden="true" />
  </button>)}</div>;
}
export function Dialog({ title, onClose, children, busy = false, className = '', modal = true }: { title: string; onClose: () => void; children: ReactNode; busy?: boolean; className?: string; modal?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null); const { t } = useTranslation(); const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null; const dialog = ref.current!;
    const position = () => {
      if (modal) return;
      const panel = dialog.closest('.assistant-panel')?.getBoundingClientRect();
      const beside = !!panel && panel.left > 660;
      const width = Math.min(620, beside ? panel.left - 32 : window.innerWidth - 24);
      dialog.style.width = width + 'px';
      dialog.style.left = (beside ? panel.left - width - 16 : 12) + 'px';
      dialog.style.top = (beside ? Math.max(12, Math.min(panel.top, 92)) : 12) + 'px';
    };
    if (modal) dialog.showModal(); else { dialog.show(); position(); window.addEventListener('resize', position); }
    return () => { window.removeEventListener('resize', position); dialog.close(); previous?.focus(); };
  }, [modal]);
  return <dialog ref={ref} className={'dialog ' + className} aria-labelledby={titleId} onCancel={e => { e.preventDefault(); if (!busy) onClose(); }} onClick={e => { if (e.target === ref.current && !busy) onClose(); }}>
    <div className="dialog-inner"><div className="dialog-header"><h2 id={titleId}>{title}</h2><button className="icon-button" aria-label={t('close')} disabled={busy} onClick={onClose}><X size={21} /></button></div>{children}</div>
  </dialog>;
}
