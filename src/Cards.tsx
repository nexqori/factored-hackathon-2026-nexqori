import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { CreditCard, Eye, EyeOff, ShieldCheck, LockKeyhole } from 'lucide-react';
import { api, ApiError } from './api';
import { Dialog } from './components';
import './cards.css';
import { CardBlockDialog } from './CardBlockDialog';

type Card = { blockRequiresEmail: boolean; id: string; last4: string; holder: string; expiryMonth: number | null; expiryYear: number | null; canReveal: boolean; canBlock: boolean; status: string };
type Details = { number: string; cvv: string; expiresAt: number; expiryMonth: number; expiryYear: number; cvvExpiresAt: number; serverTime: number; revealToken: string; hideDeadline: number; cvvDeadline: number };
export type CardAction = { action: 'reveal' | 'block'; last4?: string | null; name?:string|null; selectedId?:string; nonce: string };

function CardView({ card, onBlocked, request, cards, onSelect }: { card: Card; onBlocked: () => void; request?: CardAction; cards:Card[]; onSelect:(id:string)=>void }) {
  const { t } = useTranslation();
  const [details, setDetails] = useState<Details | null>(null);
  const [ask, setAsk] = useState(false); const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const [remaining, setRemaining] = useState(0);
  const [cvvRemaining, setCvvRemaining] = useState(0);
  const [blockOpen, setBlockOpen] = useState(false);
  const generation = useRef(0);
  function hide() { generation.current++; setDetails(null); setPassword(''); setAsk(false); }
  function openBlock() { hide(); setError(''); setBlockOpen(true); }
  useEffect(() => {
    if (!request) { hide();setBlockOpen(false);return; }
    if (request.action === 'block' && card.canBlock) openBlock();
    else if (request.action === 'reveal' && card.canReveal) { hide(); setBlockOpen(false);  setError(''); setAsk(true); }
  }, [request?.nonce]);
  useEffect(() => {
    const conceal = () => { generation.current++; setDetails(null); setPassword(''); setAsk(false); };
    const hidden = () => { if (document.hidden) conceal(); };
    window.addEventListener('blur', conceal); document.addEventListener('visibilitychange', hidden);
    return () => { generation.current++; window.removeEventListener('blur', conceal); document.removeEventListener('visibilitychange', hidden); };
  }, []);
  useEffect(() => {
    if (!details) return;
    const controller = new AbortController(); let refreshing = false;
    const current = generation.current;
    const tick = () => {
      const seconds = Math.max(0, Math.ceil((details.hideDeadline - performance.now()) / 1000));
      const cvvSeconds = Math.max(0, Math.ceil((details.cvvDeadline - performance.now()) / 1000));
      setRemaining(seconds); setCvvRemaining(cvvSeconds);
      if (!seconds) { hide(); return; }
      if (!cvvSeconds && !refreshing) {
        refreshing = true; const started = performance.now();
        void api<Pick<Details,'cvv'|'cvvExpiresAt'|'serverTime'>>('/cards/' + encodeURIComponent(card.id) + '/cvv', 'POST', {revealToken:details.revealToken}, controller.signal)
          .then(next => { if (current === generation.current && !document.hidden && performance.now() < details.hideDeadline) setDetails({...details,...next,cvvDeadline:started + (next.cvvExpiresAt-next.serverTime)*1000}); })
          .catch(() => { if (!controller.signal.aborted && current === generation.current) hide(); });
      }
    };
    tick(); const timer = window.setInterval(tick, 250); return () => { clearInterval(timer); controller.abort(); };
  }, [details]);
  async function reveal(e: FormEvent) {
    e.preventDefault(); if (busy || (request && !request.selectedId)) return; setBusy(true); setError('');
    const current = ++generation.current;
    const submittedPassword = password; setPassword('');
    const started = performance.now();
    try {
      const result = await api<Details>('/cards/' + encodeURIComponent(card.id) + '/reveal', 'POST', { password: submittedPassword });
      if (current === generation.current && !document.hidden && performance.now() < started + (result.expiresAt-result.serverTime)*1000) { setDetails({...result,hideDeadline:started+(result.expiresAt-result.serverTime)*1000,cvvDeadline:started+(result.cvvExpiresAt-result.serverTime)*1000}); setAsk(false); }
    } catch (e) { if (current === generation.current) setError(t(e instanceof ApiError && ['card_password','card_unavailable','card_expired','card_blocked','rate_limited'].includes(e.code) ? 'error.' + e.code : 'error.generic')); }
    finally { setBusy(false); }
  }
  return <article className="card-workspace" data-card-id={card.id}>
    <div className="bank-card">
      <div className="card-top"><strong>nexqori.</strong><CreditCard size={28} aria-hidden="true" /></div>
      <p>{t('cardName')}</p>
      {card.status === 'blocked' && <p className="card-blocked-label" role="status"><LockKeyhole size={16}/>{t('cardBlocked')}</p>}
      <div className="card-number" aria-label={t('cardNumber')}>{details ? details.number.match(/.{1,4}/g)?.join(' ') : '•••• •••• •••• ' + card.last4}</div>
      <dl className="card-fields"><div><dt>{t('cardHolder')}</dt><dd>{card.holder}</dd></div><div><dt>{t('cardExpiry')}</dt><dd data-testid="card-expiry">{details ? String(details.expiryMonth).padStart(2, '0') + '/' + String(details.expiryYear).slice(-2) : '••/••'}</dd></div></dl>
    </div>
    <div className="card-controls"><div><h2>{t('cardDetails')}</h2><p className="muted">{t(card.status === 'blocked' ? 'error.card_blocked' : 'cardPrivacy')}</p></div>
      <div className="cvv-line"><div><span>{t('dynamicCvv')}</span><strong data-testid="card-cvv">{details && cvvRemaining > 0 ? details.cvv : '•••'}</strong></div>{details && <span data-testid="card-cvv-renewal">{t('cardCvvRenewal', {time:Math.floor(cvvRemaining/60)+':'+String(cvvRemaining%60).padStart(2,'0')})}</span>}</div>
      {details && <p data-testid="card-hide-timer" className="muted">{t('cardRevealTimer', {count:remaining})}</p>}
      <button className="button primary" disabled={!card.canReveal} onClick={() => { if (details) hide(); else { setError(''); setAsk(true); } }}>{details ? <EyeOff size={18} /> : <Eye size={18} />}{t(details ? 'hideCardDetails' : 'showCardDetails')}</button>
      {!card.canReveal && card.status !== 'blocked' && <p className="muted">{t('error.card_unavailable')}</p>}
      {card.canBlock && <button className="button secondary" onClick={openBlock}><LockKeyhole size={18}/>{t('blockCard')}</button>}
      <Link className="text-link" to={'/movements?product=' + encodeURIComponent(card.id)}>{t('seeMovements')}</Link>
      <p className="card-security"><ShieldCheck size={18} />{t('cardSecretHint')}</p>
    </div>
    {ask && <Dialog title={t('confirmIdentity')} onClose={hide} busy={busy}><form onSubmit={reveal} className="form-stack"><p>{t('cardReauth')}</p>{request&&<label>{t('cardSelection')}<select required disabled={busy} value={request.selectedId||''} onChange={e=>{setPassword('');onSelect(e.target.value);}}><option value="">{t('chooseOption')}</option>{cards.filter(c=>c.canReveal).map(c=><option key={c.id} value={c.id}>{t('cardName')} · {c.last4}</option>)}</select></label>}<label>{t('password')}<input autoFocus type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={e => setPassword(e.target.value)} /></label>{error && <p role="alert" className="error-text">{error}</p>}<button className="button primary" disabled={busy}>{t(busy ? 'loading' : 'showCardDetails')}</button></form></Dialog>}
    {blockOpen && <CardBlockDialog card={card} onClose={()=>setBlockOpen(false)} onBlocked={()=>{hide();setBlockOpen(false);onBlocked();}}/>}
  </article>;
}

export function Cards({ onChanged, action, onActionConsumed }: { onChanged?: () => void; action?: CardAction | null; onActionConsumed?: () => void }) {
  const { t } = useTranslation(); const [cards, setCards] = useState<Card[]>([]); const [status, setStatus] = useState('loading');
  const [pending, setPending] = useState<(CardAction & {id:string}) | null>(null);
  const [choices,setChoices] = useState<{action:CardAction;cards:Card[]} | null>(null);
  const [actionError,setActionError] = useState(false); const handled = useRef('');
  useEffect(() => {
    if (!action || status !== 'ready' || handled.current === action.nonce) return;
    handled.current = action.nonce; setActionError(false);
    const eligible=cards.filter(c=>action.action==='reveal'?c.canReveal:c.canBlock);
    const normalize=(v:string)=>v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    const available=eligible.filter(c=>(!action.last4||c.last4===action.last4)&&(!action.name||[normalize(t('cardName')), 'nexqori',c.last4].includes(normalize(action.name))));
    if(action.action==='reveal'&&eligible.length){
      const selected=available.length===1?available[0]:null;
      setPending({...action,id:selected?.id||eligible[0].id,selectedId:selected?.id||''});onActionConsumed?.();return;
    }
    if (available.length === 1) setPending({...action,id:available[0].id,selectedId:available[0].id});
    else if (available.length > 1) setChoices({action,cards:available});
    else setActionError(true);
    onActionConsumed?.();
  }, [action,status,cards,onActionConsumed]);
  useEffect(() => { const controller = new AbortController(); api<{ cards: Card[] }>('/cards', 'GET', undefined, controller.signal).then(data => { setCards(data.cards); setStatus('ready'); }).catch(() => { if (!controller.signal.aborted) setStatus('error'); }); return () => controller.abort(); }, []);
  return <section><div className="page-heading"><h1>{t('cards')}</h1><p>{t('cardsIntro')}</p></div>{actionError&&<p role="alert">{t('cardActionUnavailable')}</p>}{choices&&<Dialog title={t('cardChooseAction')} onClose={()=>setChoices(null)}><div className="form-stack">{choices.cards.map(card=><button className="button secondary" key={card.id} onClick={()=>{setPending({...choices.action,id:card.id,selectedId:card.id});setChoices(null);}}>{t('card')} · •••• {card.last4}</button>)}</div></Dialog>}{status === 'loading' ? <p role="status">{t('loading')}</p> : status === 'error' ? <p role="alert">{t('error.generic')}</p> : cards.length ? cards.map(card => <CardView cards={cards} onSelect={id=>{if(pending)setPending({...pending,id:id||cards.find(c=>c.canReveal)!.id,selectedId:id,nonce:crypto.randomUUID()});}} card={card} request={pending?.id===card.id?pending:undefined} key={card.id} onBlocked={() => { setCards(old => old.map(c => c.id === card.id ? { ...c, status: 'blocked', canReveal: false, canBlock: false } : c)); onChanged?.(); }} />) : <p className="empty-panel">{t('noCards')}</p>}</section>;
}
