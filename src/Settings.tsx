import { Check, SlidersHorizontal } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import { NotificationSettings } from './NotificationSettings';
import { ExperienceSettings } from './Experience';
import type { TextSize, User } from './types';

export function Settings({ user, setUser }: { user: User; setUser: (user: User) => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [selected, setSelected] = useState(user.textSize);
  async function choose(textSize: TextSize) {
    setBusy(true); setStatus(''); setSelected(textSize);
    try { const result = await api<{ user: User }>('/profile/preferences', 'PATCH', { textSize }); setUser(result.user); setStatus('preferencesSaved'); }
    catch (e) { setSelected(user.textSize); setStatus('error.' + (e instanceof ApiError ? e.code : 'generic')); }
    finally { setBusy(false); }
  }
  return <><div className="page-heading"><p className="eyebrow">NEXQORI</p><h1>{t('settings')}</h1><p>{t('settingsIntro')}</p></div><section className="panel settings-panel"><span className="round-icon"><SlidersHorizontal size={22} /></span><h2>{t('readingTitle')}</h2><p className="muted">{t('readingDescription')}</p><fieldset className="size-options" disabled={busy}><legend>{t('textSize')}</legend>{(['small', 'medium', 'large'] as const).map(size => <label className={selected === size ? 'selected' : ''} key={size}><input type="radio" name="textSize" value={size} checked={selected === size} onChange={() => { void choose(size); }} /><span className={'size-sample size-' + size} aria-hidden="true">Aa</span><span>{t('textSize.' + size)}</span>{selected === size && <Check size={16} aria-hidden="true" />}</label>)}</fieldset><div className="reading-preview"><strong>{t('readingPreview')}</strong><p>{t('readingExample')}</p></div>{status && <p className={status.startsWith('error.') ? 'error-text' : 'settings-saved'} role="status">{t(status)}</p>}</section>{user.role === 'customer' && <><NotificationSettings/><ExperienceSettings user={user} setUser={setUser} /></>}</>;
}
