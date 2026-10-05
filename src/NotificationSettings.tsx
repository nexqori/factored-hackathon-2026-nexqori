import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Mail, ShieldCheck } from 'lucide-react';
import { api, ApiError } from './api';

export type EmailCode = { challengeId: string; destination: string; expiresAt: number; resendAt: number };
export function useCodeClock() {
  const [stamp, setStamp] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => { const timer = window.setInterval(() => setStamp(Math.floor(Date.now() / 1000)), 1000); return () => clearInterval(timer); }, []);
  return stamp;
}

export function NotificationSettings() {
  const { t } = useTranslation(); const stamp = useCodeClock();
  const [current, setCurrent] = useState<string | null>(null); const [email, setEmail] = useState('');
  const [password, setPassword] = useState(''); const [code, setCode] = useState('');
  const [challenge, setChallenge] = useState<EmailCode | null>(null);
  const [ready, setReady] = useState(false); const [available, setAvailable] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setReady(false); setError('');
    void api<{email:string|null;suggestedEmail?:string;mailAvailable:boolean}>('/profile/notifications', 'GET', undefined, abort.signal).then(result => {
      setCurrent(result.email); setEmail(result.email || result.suggestedEmail || ''); setAvailable(result.mailAvailable); setReady(true);
    }).catch(e => { if (!abort.signal.aborted) setError('error.' + (e instanceof ApiError ? e.code : 'generic')); });
    return () => abort.abort();
  }, [reload]);
  async function send(e: FormEvent) {
    e.preventDefault(); if (busy) return; setBusy(true); setError(''); setSaved(false);
    try { setChallenge(await api<EmailCode>('/profile/notifications/code', 'POST', { email, password })); setPassword(''); setCode(''); }
    catch (e) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
    finally { setBusy(false); }
  }
  async function verify(e: FormEvent) {
    e.preventDefault(); if (busy || !challenge) return; setBusy(true); setError('');
    try { const result = await api<{email:string}>('/profile/notifications/verify', 'POST', { challengeId: challenge.challengeId, code }); setCurrent(result.email); setEmail(result.email); setChallenge(null); setCode(''); setSaved(true); }
    catch (e) { setError('error.' + (e instanceof ApiError ? e.code : 'generic')); }
    finally { setBusy(false); }
  }
  return <section className="panel settings-panel notification-settings" aria-label={t('notifications.title')}>
    <span className="round-icon"><Mail size={22}/></span><h2>{t('notifications.title')}</h2><p>{t('notifications.intro')}</p>
    {current && <p className="info-banner"><ShieldCheck size={17} aria-hidden="true"/> {t('notifications.verified', {email:current})}</p>}
    {!ready && !error && <p role="status">{t('loading')}</p>}
    {!ready && error && <button className="button secondary" onClick={() => setReload(n=>n+1)}>{t('retry')}</button>}
    {ready && !available && <p className="info-banner">{t('error.mail_unavailable')}</p>}
    {ready && (!challenge ? <form className="form-stack" onSubmit={send}>
      <label>{t('notifications.email')}<input type="email" autoComplete="email" maxLength={254} required value={email} disabled={busy} onChange={e=>{setEmail(e.target.value);setSaved(false);}}/></label>
      <label>{t('password')}<input type="password" autoComplete="current-password" maxLength={256} required value={password} disabled={busy} onChange={e=>setPassword(e.target.value)}/></label>
      <button className="button primary" disabled={busy || !available || current === email}>{t(busy ? 'loading' : 'notifications.verifyAddress')}</button>
    </form> : <form className="form-stack" onSubmit={verify}>
      <p role="status">{t('notifications.codeSent',{email:challenge.destination})}</p><p className="muted">{t('notifications.codeHint')}</p>
      <label>{t('notifications.code')}<input inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} disabled={busy} onChange={e=>setCode(e.target.value.replace(/\D/g,''))}/></label>
      {stamp >= challenge.expiresAt && <p role="status">{t('notifications.expired')}</p>}
      <button className="button primary" disabled={busy || code.length !== 6 || stamp >= challenge.expiresAt}>{t(busy ? 'loading' : 'notifications.confirmEmail')}</button>
      <button type="button" className="button secondary" disabled={busy} onClick={()=>{setChallenge(null);setCode('');setError('');}}>{t('notifications.changeOrResend')}</button>
    </form>)}
    {error && <p role="alert" className="error-text">{t(error)}</p>}{saved && <p role="status" className="settings-saved">{t('notifications.saved')}</p>}
  </section>;
}
