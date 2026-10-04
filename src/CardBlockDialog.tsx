import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { api, ApiError } from './api';
import { Dialog } from './components';
import { useCodeClock, type EmailCode } from './NotificationSettings';

export function CardBlockDialog({card,onClose,onBlocked}:{card:{id:string;last4:string;blockRequiresEmail:boolean};onClose:()=>void;onBlocked:()=>void}) {
  const {t}=useTranslation(); const stamp=useCodeClock();
  const [password,setPassword]=useState('');const [code,setCode]=useState('');const [confirmed,setConfirmed]=useState(false);
  const [challenge,setChallenge]=useState<EmailCode|null>(null);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const requestKey=useRef(crypto.randomUUID()); const locked=useRef(false);
  async function send(){
    if(locked.current)return;locked.current=true;setBusy(true);setError('');
    try{setChallenge(await api<EmailCode>('/cards/'+encodeURIComponent(card.id)+'/block-code','POST',{password}));setCode('');}
    catch(e){setError('error.'+(e instanceof ApiError?e.code:'generic'));}
    finally{locked.current=false;setBusy(false);}
  }
  async function submit(e:FormEvent){
    e.preventDefault();if(locked.current)return;
    if(card.blockRequiresEmail&&!challenge){await send();return;}
    if(!confirmed)return;locked.current=true;setBusy(true);setError('');
    try{await api('/cards/'+encodeURIComponent(card.id)+'/block','POST',{password,confirmed:true,requestKey:requestKey.current,...(challenge?{challengeId:challenge.challengeId,code}:{})});setPassword('');setCode('');onBlocked();onClose();}
    catch(e){setError('error.'+(e instanceof ApiError?e.code:'generic'));}
    finally{locked.current=false;setBusy(false);}
  }
  return <Dialog title={t('blockCard')} onClose={onClose} busy={busy}><form onSubmit={submit} className="form-stack">
    <p>{t('blockCardExplain',{last4:card.last4})}</p>
    {!challenge&&<label>{t('password')}<input type="password" autoComplete="current-password" required maxLength={256} value={password} disabled={busy} onChange={e=>setPassword(e.target.value)}/></label>}
    {card.blockRequiresEmail&&!challenge&&<p>{t('notifications.blockIntro')}</p>}
    {challenge&&<><p role="status">{t('notifications.codeSent',{email:challenge.destination})}</p><p className="muted">{t('notifications.codeHint')}</p><label>{t('notifications.code')}<input autoFocus inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} disabled={busy} onChange={e=>setCode(e.target.value.replace(/\D/g,''))}/></label>{stamp>=challenge.expiresAt&&<p role="status">{t('notifications.expired')}</p>}<button className="button secondary" type="button" disabled={busy||stamp<challenge.resendAt} onClick={()=>void send()}>{t('notifications.resend')}{stamp<challenge.resendAt?' · '+(challenge.resendAt-stamp)+' s':''}</button></>}
    {(!card.blockRequiresEmail||challenge)&&<label className="checkbox-label"><input type="checkbox" required disabled={busy} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('blockCardConfirm')}</label>}
    {error&&<p className="error-text" role="alert">{t(error)}</p>}
    {error==='error.notification_email_required'&&<Link className="button secondary" to="/settings" onClick={onClose}>{t('notifications.configure')}</Link>}
    <button className="button primary" disabled={busy||((!!challenge||!card.blockRequiresEmail)&&!confirmed)|| (!!challenge&&(code.length!==6||stamp>=challenge.expiresAt))}>{t(busy?'loading':card.blockRequiresEmail&&!challenge?'notifications.sendCode':'confirmBlockCard')}</button>
  </form></Dialog>;
}
