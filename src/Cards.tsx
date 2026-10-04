import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { CreditCard, Eye, EyeOff, ShieldCheck, LockKeyhole } from 'lucide-react';
import { api, ApiError } from './api';
import { Dialog } from './components';
import './cards.css';
import { CardBlockDialog } from './CardBlockDialog';

type Card = { blockRequiresEmail: boolean; id: string; last4: string; holder: string; expiryMonth: number | null; expiryYear: number | null; canReveal: boolean; canBlock: boolean; status: string };
type Details = { number: string; cvv: string; expiresAt: number };

function CardView({ card, onBlocked }: { card: Card; onBlocked: () => void }) {
  const { t } = useTranslation();
  const [details, setDetails] = useState<Details | null>(null);
  const [ask, setAsk] = useState(false); const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [remaining, setRemaining] = useState(0);
  const [blockOpen, setBlockOpen] = useState(false);
  const generation = useRef(0);
  function hide() { generation.current++; setDetails(null); setPassword(''); setAsk(false); }
  useEffect(() => {
    const conceal = () => { generation.current++; setDetails(null); setPassword(''); setAsk(false); };
    const hidden = () => { if (document.hidden) conceal(); };
    window.addEventListener('blur', conceal); document.addEventListener('visibilitychange', hidden);
    return () => { generation.current++; window.removeEventListener('blur', conceal); document.removeEventListener('visibilitychange', hidden); };
  }, []);
  useEffect(() => {
    if (!details) return;
    const tick = () => { const seconds = Math.max(0, details.expiresAt - Math.floor(Date.now() / 1000)); setRemaining(seconds); if (!seconds) setDetails(null); };
    tick(); const timer = window.setInterval(tick, 1000); return () => clearInterval(timer);
  }, [details]);
  async function reveal(e: FormEvent) {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    const current = ++generation.current;
    const submittedPassword = password; setPassword('');
    try {
      const result = await api<Details>('/cards/' + encodeURIComponent(card.id) + '/reveal', 'POST', { password: submittedPassword });
      if (current === generation.current && !document.hidden) { setDetails(result); setAsk(false); }
    } catch (e) { if (current === generation.current) setError(t(e instanceof ApiError && ['card_password','card_unavailable','card_expired','card_blocked','rate_limited'].includes(e.code) ? 'error.' + e.code : 'error.generic')); }
    finally { setBusy(false); }
  }
  return <article className="card-workspace">
    <div className="bank-card">
      <div className="card-top"><strong>nexqori.</strong><CreditCard size={28} aria-hidden="true" /></div>
      <p>{t('card')}</p>
      {card.status === 'blocked' && <p className="card-blocked-label" role="status"><LockKeyhole size={16}/>{t('cardBlocked')}</p>}
      <div className="card-number" aria-label={t('cardNumber')}>{details ? details.number.match(/.{1,4}/g)?.join(' ') : '•••• •••• •••• ' + card.last4}</div>
      <dl className="card-fields"><div><dt>{t('cardHolder')}</dt><dd>{card.holder}</dd></div><div><dt>{t('cardExpiry')}</dt><dd>{card.expiryMonth && card.expiryYear ? String(card.expiryMonth).padStart(2, '0') + '/' + String(card.expiryYear).slice(-2) : '—'}</dd></div></dl>
    </div>
    <div className="card-controls"><div><h2>{t('cardDetails')}</h2><p className="muted">{t(card.status === 'blocked' ? 'error.card_blocked' : 'cardPrivacy')}</p></div>
      <div className="cvv-line"><div><span>{t('dynamicCvv')}</span><strong data-testid="card-cvv">{details?.cvv ?? '•••'}</strong></div>{details && <span>{t('cardSeconds', { count: remaining })}</span>}</div>
      <button className="button primary" disabled={!card.canReveal} onClick={() => { if (details) hide(); else { setError(''); setAsk(true); } }}>{details ? <EyeOff size={18} /> : <Eye size={18} />}{t(details ? 'hideCardDetails' : 'showCardDetails')}</button>
      {!card.canReveal && card.status !== 'blocked' && <p className="muted">{t('error.card_unavailable')}</p>}
      {card.canBlock && <button className="button secondary" onClick={() => { hide(); setError(''); setBlockOpen(true); }}><LockKeyhole size={18}/>{t('blockCard')}</button>}
      <Link className="text-link" to={'/movements?product=' + encodeURIComponent(card.id)}>{t('seeMovements')}</Link>
      <p className="card-security"><ShieldCheck size={18} />{t('cardSecretHint')}</p>
    </div>
    {ask && <Dialog title={t('confirmIdentity')} onClose={hide} busy={busy}><form onSubmit={reveal} className="form-stack"><p>{t('cardReauth')}</p><label>{t('password')}<input autoFocus type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={e => setPassword(e.target.value)} /></label>{error && <p role="alert" className="error-text">{error}</p>}<button className="button primary" disabled={busy}>{t(busy ? 'loading' : 'showCardDetails')}</button></form></Dialog>}
    {blockOpen && <CardBlockDialog card={card} onClose={()=>setBlockOpen(false)} onBlocked={()=>{hide();onBlocked();}}/>}
  </article>;
}

export function Cards({ onChanged }: { onChanged?: () => void }) {
  const { t } = useTranslation(); const [cards, setCards] = useState<Card[]>([]); const [status, setStatus] = useState('loading');
  useEffect(() => { const controller = new AbortController(); api<{ cards: Card[] }>('/cards', 'GET', undefined, controller.signal).then(data => { setCards(data.cards); setStatus('ready'); }).catch(() => { if (!controller.signal.aborted) setStatus('error'); }); return () => controller.abort(); }, []);
  return <section><div className="page-heading"><h1>{t('cards')}</h1><p>{t('cardsIntro')}</p></div>{status === 'loading' ? <p role="status">{t('loading')}</p> : status === 'error' ? <p role="alert">{t('error.generic')}</p> : cards.length ? cards.map(card => <CardView card={card} key={card.id} onBlocked={() => { setCards(old => old.map(c => c.id === card.id ? { ...c, status: 'blocked', canReveal: false, canBlock: false } : c)); onChanged?.(); }} />) : <p className="empty-panel">{t('noCards')}</p>}</section>;
}
