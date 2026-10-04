import {useEffect,useId,useMemo,useRef,useState,type CSSProperties} from 'react';
import {useTranslation} from 'react-i18next';
import {Mic,MicOff,PhoneOff,Volume2} from 'lucide-react';
import {api,ApiError} from './api';
import {VoiceClient,type VoiceCapabilities,type VoiceSelection} from './voiceClient';
import {groupVoiceTranscript,type VoiceFragment} from './voiceTranscript';
import {useVoiceActivity} from './useVoiceActivity';
import type {ChatReply} from './AssistantPanel';

export function VoiceCall({selection,onReply,onClose,onSession}:{selection:Omit<VoiceSelection,'voice'>;onReply:(reply:ChatReply)=>void;onClose:()=>void;onSession:(id:string)=>void}){
  const {t}=useTranslation();const [capability,setCapability]=useState<VoiceCapabilities|null>(null);
  const voiceId=useId();
  const agentDescriptionId=useId();
  const [state,setState]=useState('ready');const [error,setError]=useState('');const [voice,setVoice]=useState('marin');
  const [muted,setMuted]=useState(false);const [fragments,setFragments]=useState<VoiceFragment[]>([]);
  const [bankReply,setBankReply]=useState('');
  const audio=useRef<HTMLAudioElement>(null);const client=useRef<VoiceClient|null>(null);
  const heading=useRef<HTMLHeadingElement>(null);const body=useRef<HTMLDivElement>(null);
  const follow=useRef(true);const callback=useRef(onReply);callback.current=onReply;
  const level=useVoiceActivity(audio,state==='active');
  const transcript=useMemo(()=>groupVoiceTranscript(fragments),[fragments]);
  useEffect(()=>{
    heading.current?.focus();
    const c=new AbortController();
    void api<VoiceCapabilities>('/voice/capabilities','GET',undefined,c.signal).then(setCapability)
      .catch(e=>{if(!c.signal.aborted)setError(e instanceof ApiError?e.code:'voice_connection');});
    return()=>{c.abort();void client.current?.stop();};
  },[]);
  useEffect(()=>{if(follow.current&&body.current)body.current.scrollTop=body.current.scrollHeight;},[fragments,bankReply]);
  async function start(){
    if(!audio.current||!capability?.enabled)return;
    setError('');setMuted(false);setFragments([]);setBankReply('');follow.current=true;
    client.current=new VoiceClient({status:setState,error:setError,
      caption:fragment=>setFragments(items=>[...items,fragment].slice(-400)),
      reply:r=>{setBankReply(r.text);callback.current(r);},session:onSession},audio.current);
    await client.current.start({...selection,voice});
  }
  async function closePrevious(){
    if(!capability?.pendingSessionId)return;setError('');
    try{await api('/voice/sessions/'+capability.pendingSessionId+'/close','POST',{});setCapability(await api<VoiceCapabilities>('/voice/capabilities'));}
    catch(e){setError(e instanceof ApiError?e.code:'voice_connection');}
  }
  async function resumeAudio(){
    try{await audio.current?.play();setError('');}catch{setError('voice_playback');}
  }
  const running=state==='active'||state==='connecting';
  const status=!capability?(error?'voiceCall.unavailable':'loading'):!capability.enabled?'voiceCall.unavailable':
    state==='active'?(level>0?'voiceCall.speaking':muted?'voiceCall.muted':'voiceCall.active'):'voiceCall.'+state;
  return <section className="voice-call" aria-label={t('voiceTitle')} data-speaking={level>0}>
    <header className="voice-call-heading">
      <h3 ref={heading} tabIndex={-1}>{t('voiceTitle')}</h3>
      <div className="voice-agent-stage" aria-hidden="true" style={{'--voice-level':level} as CSSProperties}>
        <div className="voice-agent-orbit"><img src="/nexqori-bot.png" alt=""/></div>
        <div className="voice-agent-wave">{[0,1,2,3,4,5,6].map(i=><span key={i} style={{'--bar':i} as CSSProperties}/>)}</div>
      </div>
      <p className="voice-agent-name">{t('voiceCall.agent')} · {voice.charAt(0).toUpperCase()+voice.slice(1)}</p>
      <p className="voice-call-status" role="status">{t(status)}</p>
    </header>
    <div className="voice-call-body" ref={body} tabIndex={0} role="region" aria-label={t(running||transcript.length?'voiceCall.transcript':'voiceCall.about')} onScroll={()=>{const el=body.current;if(el)follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<70;}}>
      {!running&&<div className="voice-call-setup">
        <div><label htmlFor={voiceId}>{t('voiceCall.agent')}</label><select id={voiceId} aria-describedby={agentDescriptionId} value={voice} onChange={e=>setVoice(e.target.value)}>{(capability?.voices||['marin']).map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}</select></div>
        <p id={agentDescriptionId} className="voice-agent-description">{t('voiceCall.agent.'+voice,{defaultValue:t('voiceCall.agent.marin')})}</p>
        <details className="voice-call-info"><summary>{t('voiceCall.about')}</summary><p className="muted">{t('voiceCall.intro')}</p></details>
      </div>}
      {(running||transcript.length>0)&&<>
        <p className="voice-transcript-hint">{t('voiceCall.captionsHint')}</p>
        <div className="voice-transcript" role="log" aria-label={t('voiceCall.transcript')} aria-live="polite" aria-relevant="additions text">
          {!transcript.length&&<p className="voice-transcript-empty">{t('voiceCall.waiting')}</p>}
          {transcript.map(row=><div key={row.id} className={'voice-transcript-row '+row.speaker}>
            <strong>{t(row.speaker==='user'?'voiceCall.heard':'voiceCall.spoken')}</strong><p>{row.text}</p>
          </div>)}
        </div>
        {bankReply&&<details className="voice-bank-result"><summary>{t('voiceCall.bankResult')}</summary><p className="voice-bank-text">{bankReply}</p><small>{t('voiceCall.screen')}</small></details>}
      </>}
    </div>
    <audio ref={audio} aria-label={t('voiceCall.audio')}/>
    <footer className="voice-call-footer">
      {error&&<p className="error-text" role="alert">{t('error.'+error,{defaultValue:t('error.voice_connection')})}</p>}
      {running&&error==='voice_playback'&&<button className="button secondary" onClick={()=>void resumeAudio()}><Volume2 size={16}/>{t('voiceCall.resumeAudio')}</button>}
      {!running&&capability?.pendingSessionId&&<button className="button secondary" onClick={()=>void closePrevious()}>{t('voiceCall.closePrevious')}</button>}
      <div className="voice-call-actions">
      {!running&&<button className="button primary" disabled={!capability?.enabled||!!capability?.pendingSessionId} onClick={()=>void start()}><Mic size={16}/>{t('voiceCall.start')}</button>}
      {state==='active'&&<button className="button secondary" aria-pressed={muted} onClick={()=>{client.current?.mute(!muted);setMuted(!muted);}}>{muted?<MicOff size={16}/>:<Mic size={16}/>} {t(muted?'voiceCall.unmute':'voiceCall.mute')}</button>}
      <button className={'button '+(running?'voice-call-end':'secondary')} onClick={()=>{void client.current?.stop();onClose();}}><PhoneOff size={16}/>{t(running?'voiceCall.end':'voiceContinue')}</button>
      </div>
    </footer>
  </section>;
}
