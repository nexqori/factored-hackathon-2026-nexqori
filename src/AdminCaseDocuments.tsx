import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ExternalLink, FileDown, FileText } from 'lucide-react';
import { api } from './api';
import { localeTags, type Locale } from './i18n';
import type { DocumentMeta } from './types';

type CaseDocument = DocumentMeta & { relation: 'request' | 'conversation' };
type DocumentPage = { documents: CaseDocument[]; nextOffset: number | null };

export function AdminCaseDocuments({ userId, requestId }: { userId: string; requestId: string }) {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const control = useRef<AbortController | null>(null);
  const path = `/admin/users/${encodeURIComponent(userId)}/requests/${encodeURIComponent(requestId)}/documents`;
  async function load(offset = 0) {
    control.current?.abort(); const abort = new AbortController(); control.current = abort;
    setBusy(true); setError(false);
    try {
      const result = await api<DocumentPage>(path + '?offset=' + offset, 'GET', undefined, abort.signal);
      setPage(old => offset && old ? { ...result, documents: [...old.documents, ...result.documents] } : result);
    } catch { if (!abort.signal.aborted) setError(true); }
    finally { if (!abort.signal.aborted) setBusy(false); }
  }
  useEffect(() => { setPage(null); void load(); return () => control.current?.abort(); }, [path]);
  return <section className="trace-section case-documents" aria-label={t('caseAdmin.documents')}>
    <div className="trace-toolbar"><h3><FileText size={18} />{t('caseAdmin.documents')}</h3><button className="text-link" disabled={busy} onClick={() => void load()}>{t('auditRefresh')}</button></div>
    <p className="muted">{t('caseAdmin.documentHint')}</p>
    {busy && <p role="status">{t('loading')}</p>}
    {error && <div role="alert"><p>{t('trace.error')}</p><button className="button secondary" disabled={busy} onClick={() => void load(page?.nextOffset ?? 0)}>{t('retry')}</button></div>}
    {page?.documents.length === 0 && <div className="case-documents-empty"><FileText size={28} aria-hidden="true" /><h3>{t('caseAdmin.noDocuments')}</h3><p>{t('caseAdmin.noDocumentsHint')}</p></div>}
    <div className="case-document-list">{page?.documents.map(doc => {
      const url = '/api' + path + '/' + encodeURIComponent(doc.id);
      return <article className="case-document-card" key={doc.id} data-case-document={doc.id}>
        <span className="eyebrow">PDF · {t('caseAdmin.relation.' + doc.relation)}</span><h4 lang={doc.locale}>{doc.title}</h4>
        <time dateTime={doc.createdAt}>{new Intl.DateTimeFormat(localeTags[i18n.language as Locale], { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Mexico_City' }).format(new Date(doc.createdAt))}</time>
        <dl className="trace-facts">
          <div><dt>{t('documents.type')}</dt><dd>{t('documents.' + doc.kind)}</dd></div>
          <div><dt>{t('language')}</dt><dd>{({ es: 'Español', en: 'English', pt: 'Português' })[doc.locale]}</dd></div>
          {doc.details.requestId && <div><dt>{t('chatFlow.case')}</dt><dd>{doc.details.requestId}</dd></div>}
          {doc.details.accountLast4 && <div><dt>{t('product')}</dt><dd>•••• {doc.details.accountLast4}</dd></div>}
          {doc.kind === 'statement' && <div><dt>{t('documents.period')}</dt><dd>{doc.details.allHistory ? t('documents.allHistory') : `${doc.details.startDate} — ${doc.details.endDate}`}</dd></div>}
        </dl>
        <div className="case-document-actions"><a className="button primary" href={url} target="_blank" rel="noopener noreferrer" aria-label={t('caseAdmin.openPdf') + ' · ' + doc.title}><ExternalLink size={16} />{t('caseAdmin.openPdf')}</a><a className="button secondary" href={url + '?download=true'} aria-label={t('documents.download') + ' · ' + doc.title}><FileDown size={16} />{t('documents.download')}</a></div>
      </article>;
    })}</div>
    {page?.nextOffset != null && <button className="button secondary" disabled={busy} onClick={() => void load(page.nextOffset!)}>{t('loadMore')}</button>}
  </section>;
}
