import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, formatMoney } from './components';
import { ChatFlow, type FlowResult } from './ChatFlow';
import type { Conversation, Dashboard } from './types';
import type { Locale } from './i18n';

export function ChatDetails({ result, conversation, text, data, selectedTx, selectedRequest, onTx, onRequest, busy, onClose, onRegistered, initialTab }: {
  result: FlowResult | null; conversation: Conversation | null; text: string; data: Dashboard;
  selectedTx: string; selectedRequest: string; onTx: (id: string) => void; onRequest: (id: string) => void;
  busy: boolean; onClose: () => void; onRegistered: (id: string) => void; initialTab: 'progress' | 'records';
}) {
  const { t, i18n } = useTranslation(); const locale = i18n.language as Locale;
  const [tab, setTab] = useState(initialTab); const id = useId();
  const tabs = ['progress', 'records'] as const;
  return <Dialog title={t('chatDetails.title')} onClose={onClose} className="chat-details-dialog">
    <div className="chat-details-tabs" role="tablist" aria-label={t('chatDetails.title')}>
      {tabs.map((value, index) => <button key={value} id={id + '-' + value} role="tab" aria-selected={tab === value}
        aria-controls={id + '-panel'} tabIndex={tab === value ? 0 : -1} onClick={() => setTab(value)}
        onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
          if (next !== null) { event.preventDefault(); setTab(tabs[next]); document.getElementById(id + '-' + tabs[next])?.focus(); }
        }}>{t('chatDetails.' + value)}</button>)}
    </div>
    <div id={id + '-panel'} role="tabpanel" aria-labelledby={id + '-' + tab} tabIndex={0} className="chat-details-content">
      {tab === 'records' && <div className="form-stack">
        <p className="muted">{t('chatFlow.referenceHint')}</p>
        <label>{t('chooseTransaction')}<select disabled={busy || !!conversation?.transactionId} value={selectedTx} onChange={event => onTx(event.target.value)}>
          <option value="">{t('noTransaction')}</option>{data.transactions.map(tx => <option key={tx.id} value={tx.id}>{tx.merchant} · {formatMoney(tx.amountMinor,locale,tx.currency)} · {tx.id}</option>)}
        </select></label>
        {conversation?.transactionId && <p className="muted">{t('transactionContextHint')}</p>}
        <label>{t('chatFlow.case')}<select disabled={busy} value={selectedRequest} onChange={event => onRequest(event.target.value)}>
          <option value="">—</option>{data.requests.map(request => <option key={request.id} value={request.id}>{request.id} · {t(request.status)}</option>)}
        </select></label>
      </div>}
      {tab === 'progress' && (result && conversation ? <ChatFlow result={result} conversationId={conversation.id} text={text} onRegistered={onRegistered}/> : <p className="empty-copy">{t('chatDetails.empty')}</p>)}
    </div>
    <div className="chat-details-footer"><button className="button secondary" onClick={onClose}>{t('chatDetails.back')}</button></div>
  </Dialog>;
}
