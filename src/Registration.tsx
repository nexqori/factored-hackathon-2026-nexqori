import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, Check, ShieldCheck, Sprout } from 'lucide-react';
import { api, ApiError, setCsrf } from './api';
import { Brand } from './components';
import { LanguagePicker } from './LanguagePicker';
import { ExperienceFields, initialExperience } from './Experience';
import type { Locale } from './i18n';
import type { TextSize, User } from './types';
import './registration.css';

export function Registration({ onLogin, onBack }: { onLogin: (user: User) => void; onBack: () => void }) {
  const { t, i18n } = useTranslation(); const [step, setStep] = useState(0); const heading = useRef<HTMLHeadingElement>(null);
  const [identity, setIdentity] = useState({name:'',email:'',identityNumber:'',password:'',repeat:''});
  const [experience, setExperience] = useState(initialExperience); const [textSize, setTextSize] = useState<TextSize>('medium'); const [confirmed, setConfirmed] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  useEffect(() => { heading.current?.focus(); }, [step]);
  async function submit(e: FormEvent) {
    e.preventDefault(); if (busy) return; setError('');
    if (step === 0 && identity.password !== identity.repeat) { setError(t('error.password_match')); return; }
    if (step === 0) {
      const [year, month, day] = experience.birthDate.split('-').map(Number); const today = new Date();
      const age = today.getFullYear() - year - (today.getMonth() + 1 < month || today.getMonth() + 1 === month && today.getDate() < day ? 1 : 0);
      if (!Number.isFinite(age) || age > 120) { setError(t('error.birth_date')); return; }
      if (age < 18) { setError(t('error.adult_required')); return; }
    }
    if (step < 2) { setStep(step + 1); return; }
    if (!confirmed) return;
    setBusy(true);
    try {
      const { repeat: _repeat, ...fields } = identity;
      const result = await api<{user:User;csrfToken:string}>('/auth/register','POST',{...fields,...experience,textSize,locale:i18n.language as Locale,confirmed});
      setCsrf(result.csrfToken); setIdentity({name:'',email:'',identityNumber:'',password:'',repeat:''}); onLogin(result.user);
    } catch (e) { const key = 'error.' + (e instanceof ApiError ? e.code : 'generic'); setError(t(i18n.exists(key) ? key : 'error.generic')); }
    finally { setBusy(false); }
  }
  return <div className="registration-page"><header className="registration-header"><Brand /><LanguagePicker onChange={locale => { void i18n.changeLanguage(locale); }} /></header><div className="registration-layout"><aside className="registration-story"><span className="round-icon"><Sprout size={28} /></span><h1>{t('registerStory')}</h1><p>{t('registerStoryBody')}</p><ol className="registration-steps">{['registerData','registerExperience','registerReview'].map((key,i) => <li key={key} className={i===step?'current':''} aria-current={i===step?'step':undefined}><span>{i<step?<Check size={17}/>:i+1}</span>{t(key)}</li>)}</ol><p className="registration-note"><ShieldCheck size={18}/>{t('registerProfileOnly')}</p></aside>
    <section className="registration-form"><button type="button" className="text-link" disabled={busy} onClick={onBack}><ArrowLeft size={17}/>{t('backLogin')}</button><p className="eyebrow">{t('registerStep',{step:step+1})}</p><h2 tabIndex={-1} ref={heading}>{t(['registerData','registerExperience','registerReview'][step])}</h2><p className="muted">{t(['registerDataHint','experienceIntro','registerReviewHint'][step])}</p>
    <form className="form-stack" onSubmit={submit}><fieldset className="experience-fieldset" disabled={busy}>
      {step===0 && <><label>{t('fullName')}<input autoComplete="name" required minLength={2} maxLength={100} value={identity.name} onChange={e=>setIdentity({...identity,name:e.target.value})}/></label><label>{t('email')}<input type="email" autoComplete="email" autoCapitalize="none" required maxLength={254} value={identity.email} onChange={e=>setIdentity({...identity,email:e.target.value})}/></label><label>{t('identityNumber')}<input autoComplete="off" required minLength={5} maxLength={32} value={identity.identityNumber} onChange={e=>setIdentity({...identity,identityNumber:e.target.value})}/><small>{t('identityHint')}</small></label><label>{t('birthDate')}<input type="date" autoComplete="bday" required value={experience.birthDate} onChange={e=>setExperience({...experience,birthDate:e.target.value})}/><small>{t('adultPolicy')}</small></label><label>{t('password')}<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={identity.password} onChange={e=>setIdentity({...identity,password:e.target.value})}/><small>{t('registerPasswordHint')}</small></label><label>{t('repeatPassword')}<input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={identity.repeat} onChange={e=>setIdentity({...identity,repeat:e.target.value})}/></label></>}
      {step===1 && <><ExperienceFields value={experience} onChange={setExperience} includeBirth={false}/><label>{t('textSize')}<select value={textSize} onChange={e=>setTextSize(e.target.value as TextSize)}>{(['small','medium','large'] as const).map(size=><option key={size} value={size}>{t('textSize.'+size)}</option>)}</select></label></>}
      {step===2 && <><dl className="registration-review"><div><dt>{t('fullName')}</dt><dd>{identity.name}</dd></div><div><dt>{t('email')}</dt><dd>{identity.email}</dd></div><div><dt>{t('identityNumber')}</dt><dd>{identity.identityNumber}</dd></div><div><dt>{t('birthDate')}</dt><dd>{experience.birthDate}</dd></div><div><dt>{t('bankingExperience')}</dt><dd>{t('banking.'+experience.bankingExperience)}</dd></div><div><dt>{t('digitalExperience')}</dt><dd>{t('digital.'+experience.digitalExperience)}</dd></div><div><dt>{t('assistancePreference')}</dt><dd>{t('assistance.'+experience.assistance)}</dd></div><div><dt>{t('textSize')}</dt><dd>{t('textSize.'+textSize)}</dd></div></dl><label className="checkbox-label"><input type="checkbox" required checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('registerConfirm')}</label></>}
      {error && <p role="alert" className="error-text">{error}</p>}<div className="registration-actions">{step>0 && <button type="button" className="button secondary" onClick={()=>{setStep(step-1);setConfirmed(false);setError('');}}>{t('previousStep')}</button>}<button className="button primary" type="submit">{t(busy?'loading':step===2?'createProfile':'nextStep')}<ArrowRight size={17}/></button></div>
    </fieldset></form></section></div></div>;
}
