import { api, ApiError } from './api';
import type { ChatReply } from './AssistantPanel';
import type { Locale } from './i18n';
import type { VoiceFragment } from './voiceTranscript';

export type VoiceCapabilities = {enabled:boolean;maxSeconds:number;voices:string[];pendingSessionId?:string|null};
export type VoiceState = {id:string;conversationId:string;status:string;expiresAt:number;revision:number;reply:ChatReply|null;reason:string|null;remoteClosed:boolean};
export type VoiceSelection = {conversationId:string|null;transactionId:string|null;requestId:string|null;locale:Locale;voice:string};
export type VoiceCallbacks = {status:(state:string)=>void;caption:(fragment:VoiceFragment)=>void;reply:(reply:ChatReply)=>void;error:(code:string)=>void;session?:(id:string)=>void};

/** The data channel is captions-only. Tools and bank results use our server. */
export class VoiceClient {
  private peer:RTCPeerConnection|null=null; private stream:MediaStream|null=null;
  private channel:RTCDataChannel|null=null; private audio:HTMLAudioElement;
  private id:string|null=null; private timer:ReturnType<typeof setTimeout>|null=null;
  private cancelled=false; private revision=0; private captionSequence=0;
  private seen=new Set<string>(); private remaining=0;
  constructor(private callbacks:VoiceCallbacks,audio:HTMLAudioElement){this.audio=audio;}

  async start(selection:VoiceSelection){
    this.callbacks.status('connecting');
    try{
      const capability=await api<VoiceCapabilities>('/voice/capabilities');
      if(!capability.enabled)throw new ApiError('voice_unavailable',503);
      if(capability.pendingSessionId)throw new ApiError('voice_active',409);
      if(this.cancelled)return;
      if(!navigator.mediaDevices?.getUserMedia||!window.RTCPeerConnection)throw new ApiError('voice_browser',0);
      this.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true},video:false});
      if(this.cancelled){this.cleanup();return;}
      const peer=new RTCPeerConnection();this.peer=peer;
      for(const track of this.stream.getAudioTracks())peer.addTrack(track,this.stream);
      peer.ontrack=event=>{this.audio.srcObject=new MediaStream([event.track]);void this.audio.play().catch(()=>this.callbacks.error('voice_playback'));};
      peer.onconnectionstatechange=()=>{if(['failed','disconnected'].includes(peer.connectionState))void this.fail('voice_connection');};
      this.channel=peer.createDataChannel('oai-events');
      this.channel.onmessage=event=>this.receive(event.data);
      this.channel.onclose=()=>{if(!this.cancelled)void this.fail('voice_connection');};
      await peer.setLocalDescription(await peer.createOffer());
      if(peer.iceGatheringState!=='complete')await new Promise<void>((resolve,reject)=>{
        const timer=setTimeout(()=>{peer.removeEventListener('icegatheringstatechange',changed);reject(new ApiError('voice_connection',0));},10000);
        function changed(){if(peer.iceGatheringState==='complete'){clearTimeout(timer);peer.removeEventListener('icegatheringstatechange',changed);resolve();}}
        peer.addEventListener('icegatheringstatechange',changed);changed();
      });
      if(this.cancelled){this.cleanup();return;}
      const started=await api<VoiceState & {sdp:string}>('/voice/sessions','POST',{...selection,requestKey:crypto.randomUUID(),sdp:peer.localDescription?.sdp});
      this.id=started.id;this.remaining=started.expiresAt*1000;
      if(this.cancelled){await this.stop();return;}
      this.callbacks.session?.(started.conversationId);
      await peer.setRemoteDescription({type:'answer',sdp:started.sdp});
      this.callbacks.status('active');await this.poll();
    }catch(error){await this.fail(error instanceof ApiError?error.code:error instanceof DOMException&&error.name==='NotAllowedError'?'voice_permission':'voice_connection');}
  }

  private receive(raw:string){
    try{
      const event=JSON.parse(raw);if(typeof event.event_id==='string'){
        if(this.seen.has(event.event_id))return;this.seen.add(event.event_id);
        if(this.seen.size>2000){void this.fail('voice_connection');return;}
      }
      const speaker=event.type==='session.input_transcript.delta'?'user':event.type==='session.output_transcript.delta'?'assistant':null;
      if(speaker&&typeof event.delta==='string'){
        this.callbacks.caption({id:String(++this.captionSequence),speaker,text:event.delta.slice(0,4000),
          startMs:typeof event.start_ms==='number'&&Number.isFinite(event.start_ms)?event.start_ms:null,
          endMs:typeof event.end_ms==='number'&&Number.isFinite(event.end_ms)?event.end_ms:null});
      }
      if(event.type==='session.closed')void this.finishRemote();
      if(event.type==='error')void this.fail('voice_connection');
    }catch{void this.fail('voice_connection');}
  }

  private async finishRemote(){
    if(this.cancelled)return;
    this.cancelled=true;this.cleanup();
    // The media-close event can beat the next heartbeat. Deliver the final
    // authenticated bank result before the parent replaces the call panel.
    const control=new AbortController();const timeout=setTimeout(()=>control.abort(),2000);
    try{
      if(this.id){
        const state=await api<VoiceState>('/voice/sessions/'+this.id+'/heartbeat','POST',{},control.signal);
        if(state.revision>this.revision&&state.reply){this.revision=state.revision;this.callbacks.reply(state.reply);}
      }
    }catch{/* Ending a call must not depend on a final network read. */}
    finally{clearTimeout(timeout);this.callbacks.status('closed');}
  }

  private async poll(){
    if(this.cancelled||!this.id)return;
    try{
      const state=await api<VoiceState>('/voice/sessions/'+this.id+'/heartbeat','POST',{});
      if(this.cancelled)return;
      if(state.revision>this.revision&&state.reply){this.revision=state.revision;this.callbacks.reply(state.reply);}
      if(this.cancelled)return;
      if(['closed','failed'].includes(state.status)||Date.now()>=this.remaining){
        if(state.status==='failed')this.callbacks.error('voice_connection');
        await this.stop();return;
      }
      this.timer=setTimeout(()=>{void this.poll();},1500);
    }catch(error){await this.fail(error instanceof ApiError?error.code:'voice_connection');}
  }

  mute(value:boolean){for(const track of this.stream?.getAudioTracks()||[])track.enabled=!value;}
  async stop(){
    this.cancelled=true;
    // Close the remote session over both paths. Stopping local tracks alone
    // would leave the billed session alive; the server lease is a final guard.
    if(this.channel?.readyState==='open')this.channel.send(JSON.stringify({type:'session.close'}));
    this.cleanup();this.callbacks.status('closed');
    if(this.id){try{await api('/voice/sessions/'+this.id+'/close','POST',{});}catch{/* Server lease also closes abandoned sessions. */}}
  }
  private async fail(code:string){await this.stop();this.callbacks.error(code);}
  private cleanup(){
    if(this.timer)clearTimeout(this.timer);
    for(const track of this.stream?.getTracks()||[])track.stop();this.stream=null;
    if(this.channel){this.channel.onclose=null;this.channel.onmessage=null;this.channel.close();this.channel=null;}
    if(this.peer){this.peer.onconnectionstatechange=null;this.peer.ontrack=null;this.peer.close();this.peer=null;}
    this.audio.pause();this.audio.srcObject=null;
  }
}
