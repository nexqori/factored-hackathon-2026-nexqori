import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { api, ApiError } from './api';
import type { User } from './types';
import { ExperienceFields, initialExperience, type ExperienceForm } from './Experience';

export type ProfileCommand = {type:'prepare_profile';field:'birthDate'|'bankingExperience'|'digitalExperience'|'assistance'|'textSize';value?:string|null};
const options = {bankingExperience:['new','occasional','frequent'],digitalExperience:['new','learning','confident'],assistance:['auto','guided','standard'],textSize:['small','medium','large']};
const prefixes = {bankingExperience:'banking.',digitalExperience:'digital.',assistance:'assistance.',textSize:'textSize.'};

export function ChatProfile({command,onSaved,onCancel}:{command:ProfileCommand;onSaved:(user:User)=>void;onCancel:()=>void}) {
  const {t,i18n}=useTranslation(); const [value,setValue]=useState(command.value||''); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  const [review,setReview]=useState(false); const field=command.field;
  const [ready,setReady]=useState(field==='textSize'); const [missingProfile,setMissingProfile]=useState(false);
  const [initial,setInitial]=useState<ExperienceForm>(initialExperience);
  useEffect(()=>{
    if(field==='textSize')return;
    const controller=new AbortController();
    void api<{experience:unknown}>('/profile/experience','GET',undefined,controller.signal).then(result=>{setMissingProfile(!result.experience);setReady(true);})
      .catch(()=>{if(!controller.signal.aborted)setError('error.generic');});
    return()=>controller.abort();
  },[field]);
  const valid=ready&&(missingProfile?!!initial.birthDate&&!!initial.bankingExperience&&!!initial.digitalExperience:field==='birthDate'?/^\d{4}-\d{2}-\d{2}$/.test(value):options[field].includes(value));
  async function submit(e:FormEvent) {e.preventDefault();if(busy||!valid)return;if(!review){setReview(true);return;}setBusy(true);setError('');
    try {const result=await api<{user:User}>(missingProfile?'/profile/experience':'/profile/field','PATCH',missingProfile?initial:{field,value,confirmed:true});onSaved(result.user);}
    catch(e){const key='error.'+(e instanceof ApiError?e.code:'generic');setError(i18n.exists(key)?key:'error.generic');setReview(false);}
    finally{setBusy(false);}
  }
  return <form className="form-stack chat-profile" onSubmit={submit}>{!ready&&!error&&<p role="status">{t('loading')}</p>}{missingProfile?<><p>{t('chatProfile.complete')}</p><fieldset className="experience-fieldset" disabled={busy||review}><ExperienceFields value={initial} onChange={setInitial}/></fieldset></>:<label>{t(field==='assistance'?'assistancePreference':field)}{field==='birthDate'?<input type="date" required disabled={!ready||busy||review} value={value} onChange={e=>setValue(e.target.value)}/>:<select required disabled={!ready||busy||review} value={value} onChange={e=>setValue(e.target.value)}><option value="">{t('chooseOption')}</option>{options[field].map(v=><option key={v} value={v}>{t(prefixes[field]+v)}</option>)}</select>}</label>}{review&&<p>{t('chatProfile.review')}</p>}{error&&<p role="alert">{t(error)}</p>}<button className="button primary" disabled={!valid||busy}>{t(review?'chatProfile.confirm':'chatProfile.reviewButton')}</button><button type="button" className="text-link" disabled={busy} onClick={review?()=>setReview(false):onCancel}>{t(review?'chatProfile.edit':'cancel')}</button></form>;
}
