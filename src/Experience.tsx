import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import type { Experience, User } from './types';

export type ExperienceForm = { birthDate: string; bankingExperience: Experience['bankingExperience'] | ''; digitalExperience: Experience['digitalExperience'] | ''; assistance: Experience['assistance'] };
export const initialExperience: ExperienceForm = { birthDate: '', bankingExperience: '', digitalExperience: '', assistance: 'auto' };
export function ExperienceFields({ value, onChange, includeBirth = true }: { value: ExperienceForm; onChange: (next: ExperienceForm) => void; includeBirth?: boolean }) {
  const { t } = useTranslation();
  const guided = value.assistance === 'guided' || value.assistance === 'auto' && (value.bankingExperience === 'new' || ['new','learning'].includes(value.digitalExperience));
  return <>{includeBirth && <label>{t('birthDate')}<input type="date" required value={value.birthDate} onChange={e => onChange({ ...value, birthDate: e.target.value })} autoComplete="bday" /><small>{t('adultPolicy')}</small></label>}
    <label>{t('bankingExperience')}<select required value={value.bankingExperience} onChange={e => onChange({ ...value, bankingExperience: e.target.value as ExperienceForm['bankingExperience'] })}><option value="">{t('chooseOption')}</option>{(['new','occasional','frequent'] as const).map(v => <option key={v} value={v}>{t('banking.' + v)}</option>)}</select></label>
    <label>{t('digitalExperience')}<select required value={value.digitalExperience} onChange={e => onChange({ ...value, digitalExperience: e.target.value as ExperienceForm['digitalExperience'] })}><option value="">{t('chooseOption')}</option>{(['new','learning','confident'] as const).map(v => <option key={v} value={v}>{t('digital.' + v)}</option>)}</select></label>
    <label>{t('assistancePreference')}<select value={value.assistance} onChange={e => onChange({ ...value, assistance: e.target.value as ExperienceForm['assistance'] })}>{(['auto','guided','standard'] as const).map(v => <option key={v} value={v}>{t('assistance.' + v)}</option>)}</select></label>
    <p className="experience-preview">{t(value.bankingExperience && value.digitalExperience ? guided ? 'guidedPreview' : 'standardPreview' : 'experienceChoiceHint')}</p>
  </>;
}

export function ExperienceSettings({ user, setUser }: { user: User; setUser: (user: User) => void }) {
  const { t, i18n } = useTranslation(); const [form, setForm] = useState<ExperienceForm>(initialExperience); const [ready, setReady] = useState(false); const [busy, setBusy] = useState(false); const [status, setStatus] = useState('');
  useEffect(() => { const controller = new AbortController(); api<{ birthDate: string; experience: Experience | null }>('/profile/experience', 'GET', undefined, controller.signal).then(data => { setForm({ birthDate: data.birthDate, bankingExperience: data.experience?.bankingExperience || '', digitalExperience: data.experience?.digitalExperience || '', assistance: data.experience?.assistance || 'auto' }); setReady(true); }).catch(() => { if (!controller.signal.aborted) setStatus('error.generic'); }); return () => controller.abort(); }, []);
  async function save(e: FormEvent) { e.preventDefault(); if (busy) return; setBusy(true); setStatus(''); try { const data = await api<{user:User}>('/profile/experience','PATCH',form); setUser(data.user); setStatus('preferencesSaved'); } catch (e) { const key = 'error.' + (e instanceof ApiError ? e.code : 'generic'); setStatus(i18n.exists(key) ? key : 'error.generic'); } finally { setBusy(false); } }
  return <section className="panel experience-settings"><h2>{t('experienceTitle')}</h2><p className="muted">{t('experienceIntro')}</p>{user.experience && <p className="profile-band">{t('ageGroup')}: {t('ageBand.' + user.experience.ageBand)}</p>}{ready ? <form className="form-stack" onSubmit={save}><fieldset disabled={busy} className="experience-fieldset"><ExperienceFields value={form} onChange={next => { setForm(next); setStatus(''); }} /><button className="button primary">{t(busy ? 'loading' : 'saveExperience')}</button></fieldset></form> : !status && <p role="status">{t('loading')}</p>}{status && <p className={status.startsWith('error.') ? 'error-text' : 'settings-saved'} role="status">{t(status)}</p>}</section>;
}
