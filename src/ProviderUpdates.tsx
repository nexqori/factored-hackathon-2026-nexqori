import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowRight, ExternalLink, RefreshCw, Search } from 'lucide-react';
import { api } from './api';
import { localeTags, type Locale } from './i18n';
import './provider-updates.css';

type Observation = {
  priceMinor: number; previousPriceMinor: number | null; currency: string;
  effectiveDate: string; fetchedAt: string; revision: number; sourceUrl: string;
};
type Source = {
  id: string; providerName: string; planName: string; sourceUrl: string;
  status: 'disabled' | 'unavailable' | 'available' | 'not_checked';
  publishedPriceMinor: number; publishedRevision: number; needsRefresh: boolean;
  observation: Observation | null; history: Observation[];
};
type SourcePage = {
  enabled: boolean; automaticRefreshSeconds: number; cachePersistent: boolean;
  persistenceError: boolean; sources: Source[];
};

/** Admin-only source controls. Publishing cannot change a customer's bill or balance. */
export function ProviderUpdates() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState<SourcePage | null>(null);
  const [query, setQuery] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState('');
  const control = useRef<AbortController | null>(null);
  const locale = localeTags[i18n.language as Locale] || localeTags.es;
  const money = (value: number) => new Intl.NumberFormat(locale, { style: 'currency', currency: 'MXN' }).format(value / 100);
  const when = (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Mexico_City' }).format(new Date(value));
  const date = (value: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value + 'T12:00:00Z'));

  async function load(search = query) {
    control.current?.abort();
    const request = new AbortController(); control.current = request;
    setBusy(true); setError(false);
    try {
      const result = await api<SourcePage>('/admin/provider-updates?q=' + encodeURIComponent(search), 'GET', undefined, request.signal);
      setPage(result);
    } catch { if (!request.signal.aborted) setError(true); }
    finally { if (!request.signal.aborted) setBusy(false); }
  }
  useEffect(() => { void load(''); return () => control.current?.abort(); }, []);

  async function update(preset?: 'usual' | 'increase') {
    if (preset && !confirmed) return;
    setBusy(true); setError(false); setNotice('');
    try {
      if (preset) {
        await api('/admin/provider-updates/example', 'POST', { preset, confirmed: true });
        setConfirmed(false); setNotice('providerUpdates.published');
      } else {
        const result = await api<{ status: string; detectedPriceChange: boolean }>('/admin/provider-updates/refresh', 'POST', {});
        setNotice(result.status === 'available'
          ? result.detectedPriceChange ? 'providerUpdates.changeDetected' : 'providerUpdates.checked'
          : 'providerUpdates.unavailable');
      }
      await load();
    } catch { setError(true); setBusy(false); }
  }

  return <section className="provider-source-panel" aria-labelledby="provider-source-title" data-testid="provider-updates">
    <div className="provider-source-heading"><div><h2 id="provider-source-title">{t('providerUpdates.title')}</h2><p>{t('providerUpdates.subtitle')}</p></div><button className="button secondary" disabled={busy || !page?.enabled} onClick={() => void update()}><RefreshCw size={17}/>{t('providerUpdates.check')}</button></div>
    <p className="provider-source-disclosure">{t('providerUpdates.controlled')}</p>
    <form className="provider-source-search" onSubmit={event => { event.preventDefault(); void load(); }}>
      <label htmlFor="provider-source-query">{t('providerUpdates.search')}</label>
      <div><input id="provider-source-query" value={query} maxLength={100} onChange={event => setQuery(event.target.value)} placeholder={t('providerUpdates.searchHint')} /><button className="button secondary" disabled={busy}><Search size={16}/>{t('providerUpdates.find')}</button></div>
    </form>
    {busy && <p role="status">{t('loading')}</p>}
    {error && <p role="alert">{t('providerUpdates.error')}</p>}
    {notice && <p role="status" className="provider-source-notice">{t(notice)}</p>}
    {page && !page.enabled && <p>{t('providerUpdates.disabled')}</p>}
    {page?.persistenceError && <p role="alert">{t('providerUpdates.persistenceError')}</p>}
    {page?.enabled && page.sources.length === 0 && <p>{t('providerUpdates.empty')}</p>}
    {page?.sources.map(source => <article className="provider-source-card" key={source.id}>
      <div className="provider-source-heading"><div><h3>{source.providerName}</h3><p>{source.planName} · {t('providerUpdates.monthly')}</p></div><a className="text-link" href={source.sourceUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={16}/>{t('providerUpdates.openSource')}</a></div>
      <div className="provider-source-prices"><div><span>{t('providerUpdates.publishedPrice')}</span><strong>{money(source.publishedPriceMinor)}</strong></div><ArrowRight aria-hidden="true"/><div><span>{t('providerUpdates.observedPrice')}</span><strong>{source.observation ? money(source.observation.priceMinor) : '—'}</strong></div></div>
      <p className="provider-source-state">{t(source.status === 'unavailable' ? 'providerUpdates.unavailable' : source.needsRefresh ? 'providerUpdates.pending' : 'providerUpdates.current')}</p>
      {source.observation && <dl className="provider-source-facts"><div><dt>{t('providerUpdates.previous')}</dt><dd>{source.observation.previousPriceMinor == null ? '—' : money(source.observation.previousPriceMinor)}</dd></div><div><dt>{t('providerUpdates.effective')}</dt><dd>{date(source.observation.effectiveDate)}</dd></div><div><dt>{t('providerUpdates.checkedAt')}</dt><dd>{when(source.observation.fetchedAt)}</dd></div></dl>}
      <p>{t('providerUpdates.limit')}</p>
      <fieldset disabled={busy || !page.enabled}><legend>{t('providerUpdates.prepare')}</legend><label className="provider-source-confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t('providerUpdates.confirm')}</label><div className="provider-source-controls"><button type="button" className="button secondary" disabled={!confirmed} onClick={() => void update('usual')}>{t('providerUpdates.publishUsual')}</button><button type="button" className="button primary" disabled={!confirmed} onClick={() => void update('increase')}>{t('providerUpdates.publishIncrease')}</button></div></fieldset>
      {source.history.length > 0 && <details><summary>{t('providerUpdates.history', { count: source.history.length })}</summary><ol className="provider-source-history">{source.history.map(row => <li key={row.revision}><strong>{money(row.priceMinor)}</strong><span>{t('providerUpdates.effective')}: {date(row.effectiveDate)}</span><time dateTime={row.fetchedAt}>{when(row.fetchedAt)}</time></li>)}</ol></details>}
    </article>)}
    {page?.enabled && <p className="muted">{page.automaticRefreshSeconds ? t('providerUpdates.automatic', { seconds: page.automaticRefreshSeconds }) : t('providerUpdates.onDemand')}</p>}
  </section>;
}
