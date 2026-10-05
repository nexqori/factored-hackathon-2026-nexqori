import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, formatDate, formatMoney } from './components';
import { ChatFlow, type ClaimRegistration, type FlowResult } from './ChatFlow';
import { ApiError } from './api';
import { AttentionReview } from './AttentionReview';
import type { Conversation, Dashboard } from './types';
import type { Locale } from './i18n';

export type ChatSelection = { transactionId: string; requestId: string };

export function ChatDetails({ result, conversation, data, selectedTx, selectedRequest, onApply, busy, onClose, onRegistered }: {
  result: FlowResult | null; conversation: Conversation | null; data: Dashboard;
  selectedTx: string; selectedRequest: string; onApply: (selection: ChatSelection) => Promise<void>;
  busy: boolean; onClose: () => void; onRegistered: (claim: ClaimRegistration) => void;
}) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const id = useId();
  const [candidate, setCandidate] = useState(selectedTx); const [applying, setApplying] = useState(false); const [error, setError] = useState('');
  const [candidateRequest, setCandidateRequest] = useState(selectedRequest || result?.requestId || '');
  const [useMovement, setUseMovement] = useState(!!selectedTx);
  const [useCase, setUseCase] = useState(!!(selectedRequest || result?.requestId));
  const locked = !!result?.requestId;
  const transaction = useMovement ? data.transactions.find(tx => tx.id === candidate) : undefined;
  const selectedCase = useCase ? data.requests.find(request => request.id === candidateRequest) : undefined;
  const selection = { transactionId: useMovement ? candidate : '', requestId: useCase ? candidateRequest : '' };
  const valid = (!useMovement || !!candidate) && (!useCase || !!candidateRequest);
  const changed = selection.transactionId !== selectedTx || selection.requestId !== selectedRequest;
  async function apply() {
    if (!valid || busy || applying || locked) return;
    setApplying(true); setError('');
    try { if (changed) await onApply(selection); onClose(); }
    catch(e) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
    finally { setApplying(false); }
  }
  return <Dialog title={t('chatDetails.title')} onClose={onClose} busy={busy || applying} className="chat-details-dialog">
    <div className="chat-details-content">
      <section className="form-stack" aria-labelledby={id + '-records'}>
        <h3 id={id + '-records'}>{t('chatSelection.title')}</h3>
        <p className="muted">{t(locked ? 'chatSelection.locked' : 'chatSelection.hint')}</p>
        <fieldset className="chat-record-options" disabled={busy || applying || locked}>
          <legend className="sr-only">{t('chatSelection.title')}</legend>
          <label><input type="checkbox" checked={useMovement} onChange={event => { setUseMovement(event.target.checked); setError(''); }}/>{t('chatSelection.movement')}</label>
          <label><input type="checkbox" checked={useCase} onChange={event => { setUseCase(event.target.checked); setError(''); }}/>{t('chatSelection.case')}</label>
        </fieldset>
        {useMovement && <label><span id={id + '-movement-label'}>{t('chooseTransaction')}</span><select aria-labelledby={id + '-movement-label'} disabled={busy || applying || locked} value={candidate} onChange={event => { setCandidate(event.target.value); setError(''); }}>
          <option value="">{t('chatSelection.chooseMovement')}</option>{data.transactions.map(tx => <option key={tx.id} value={tx.id}>{tx.merchant} · {formatMoney(tx.amountMinor,locale,tx.currency)} · {formatDate(tx.date,locale)} · {tx.id}</option>)}
        </select></label>}
        {transaction && <dl className="detail-list chat-movement-preview" data-selected-movement={transaction.id}>
          <div><dt>{t('chatMovement.merchant')}</dt><dd>{transaction.merchant}</dd></div>
          <div><dt>{t('chatMovement.date')}</dt><dd>{formatDate(transaction.date,locale)}</dd></div>
          <div><dt>{t('chatMovement.amount')}</dt><dd>{formatMoney(transaction.amountMinor,locale,transaction.currency)}</dd></div>
          <div><dt>{t('chatMovement.reference')}</dt><dd>{transaction.id}</dd></div>
        </dl>}
        {error && <p className="error-text" role="alert">{t(i18n.exists(error) ? error : 'error.generic')}</p>}
        {useCase && <label><span id={id + '-case-label'}>{t('chatFlow.case')}</span><select aria-labelledby={id + '-case-label'} disabled={busy || applying || locked} value={candidateRequest} onChange={event => { setCandidateRequest(event.target.value); setError(''); }}>
          <option value="">{t('chatSelection.chooseCase')}</option>{data.requests.map(request => <option key={request.id} value={request.id}>{request.id} · {t(request.status)}</option>)}
        </select></label>}
        {selectedCase && <div className="chat-case-preview"><strong>{selectedCase.id} · {t(selectedCase.status)}</strong><p>{selectedCase.details}</p></div>}
      </section>
      <section className="chat-details-progress" aria-label={t('chatDetails.progress')}>
        {changed && !locked && result && <p className="muted">{t('chatSelection.pending')}</p>}
        {result && conversation ? <ChatFlow autoOpen={false} result={result} conversationId={conversation.id} onRegistered={onRegistered} readOnly={changed && !locked}/> : <p className="empty-copy">{t('chatDetails.empty')}</p>}
      </section>
    </div>
    {conversation && <AttentionReview source={result?.requestId ? 'requests' : 'conversations'} identity={result?.requestId || conversation.id}/>}
    <div className="chat-details-footer">{!locked && <button className="button primary" disabled={!valid || busy || applying} onClick={() => { void apply(); }}>{t(applying ? 'loading' : useMovement || useCase ? 'chatSelection.apply' : 'chatSelection.none')}</button>}<button className="button secondary" disabled={busy || applying} onClick={onClose}>{t('chatDetails.back')}</button></div>
  </Dialog>;
}
