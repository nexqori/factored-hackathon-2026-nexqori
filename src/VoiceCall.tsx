import {useEffect,useRef,useState} from 'react';
import {useTranslation} from 'react-i18next';
import {Mic,MicOff,PhoneOff} from 'lucide-react';
import {api,ApiError} from './api';
import {VoiceClient,type VoiceCapabilities,type VoiceSelection} from './voiceClient';
import type {ChatReply} from './AssistantPanel';

export function VoiceCall({selection,onReply,onClose,onSession}:{selection:Omit<VoiceSelection,'voice'>;onReply:(reply:ChatReply)=>void;onClose:()=>void;onSession:(id:string)=>void}){
  const {t}=useTranslation();const [capability,setCapability]=useState<VoiceCapabilities|null>(null);
  const [state,setState]=useState('ready');const [error,setError]=useState('');const [voice,setVoice]=useState('marin');
  const [muted,setMuted]=useState(false);const [caption,setCaption]=useState({speaker:'user',text:''});
  const audio=useRef<HTMLAudioElement>(null);const client=useRef<VoiceClient|null>(null);
  const callback=useRef(onReply);callback.current=onReply;
  useEffect(()=>{const c=new AbortController();void api<VoiceCapabilities>('/voice/capabilities','GET',undefined,c.signal).then(setCapability).catch(e=>{if(!c.signal.aborted)setError(e instanceof ApiError?e.code:'voice_connection');});return()=>{c.abort();void client.current?.stop();};},[]);
  async function start(){
    if(!audio.current||!capability?.enabled)return;setError('');setMuted(false);setCaption({speaker:'user',text:''});
    client.current=new VoiceClient({status:setState,error:setError,caption:(speaker,text)=>setCaption({speaker,text}),reply:r=>callback.current(r),session:onSession},audio.current);
    await client.current.start({...selection,voice});
  }
  async function closePrevious(){
    if(!capability?.pendingSessionId)return;setError('');
    try{await api('/voice/sessions/'+capability.pendingSessionId+'/close','POST',{});setCapability(await api<VoiceCapabilities>('/voice/capabilities'));}
    catch(e){setError(e instanceof ApiError?e.code:'voice_connection');}
  }
  const running=state==='active'||state==='connecting';
  return <section className="voice-call" aria-label={t('voiceTitle')}>
    <h3>{t('voiceTitle')}</h3>
    <p role="status">{t(capability?.enabled?'voiceCall.'+state:'voiceCall.unavailable')}</p>
    {!running&&<><p className="muted">{t('voiceCall.intro')}</p><label>{t('voiceCall.voice')}<select value={voice} onChange={e=>setVoice(e.target.value)}>{(capability?.voices||['marin']).map(v=><option key={v} value={v}>{v}</option>)}</select></label></>}
    {running&&<p className="muted">{t('voiceCall.screen')}</p>}
    {caption.text&&<p className="voice-caption"><strong>{t(caption.speaker==='user'?'voiceCall.you':'assistant')}: </strong>{caption.text}</p>}
    <audio ref={audio} controls={running} aria-label={t('voiceCall.audio')}/>
    {error&&<p className="error-text" role="alert">{t('error.'+error,{defaultValue:t('error.voice_connection')})}</p>}
    <div className="voice-call-actions">
      {!running&&capability?.pendingSessionId&&<button className="button secondary" onClick={()=>void closePrevious()}>{t('voiceCall.closePrevious')}</button>}
      {!running&&<button className="button primary" disabled={!capability?.enabled||!!capability?.pendingSessionId} onClick={()=>void start()}><Mic size={16}/>{t('voiceCall.start')}</button>}
      {state==='active'&&<button className="button secondary" aria-pressed={muted} onClick={()=>{client.current?.mute(!muted);setMuted(!muted);}}>{muted?<MicOff size={16}/>:<Mic size={16}/>} {t(muted?'voiceCall.unmute':'voiceCall.mute')}</button>}
      <button className="button secondary" onClick={()=>{void client.current?.stop();onClose();}}><PhoneOff size={16}/>{t(running?'voiceCall.end':'voiceContinue')}</button>
    </div>
  </section>;
}
