import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {VoiceClient} from './voiceClient';
import {api} from './api';
vi.mock('./api',async()=>{const actual=await vi.importActual('./api');return {...actual,api:vi.fn()};});

describe('optional voice client',()=>{
  const selection={conversationId:null,transactionId:null,requestId:null,locale:'es' as const,voice:'marin'};
  let peer:any,track:any,media:any,callbacks:any,audio:any;
  beforeEach(()=>{
    vi.useFakeTimers();vi.mocked(api).mockReset();
    track={stop:vi.fn(),enabled:true};media={getTracks:()=>[track],getAudioTracks:()=>[track]};
    peer={addTrack:vi.fn(),createOffer:vi.fn(async()=>({type:'offer',sdp:'v=0'})),
      setLocalDescription:vi.fn(async()=>{}),localDescription:{sdp:'v=0'},iceGatheringState:'complete',
      setRemoteDescription:vi.fn(async()=>{}),close:vi.fn(),channel:{readyState:'open',send:vi.fn(),close:vi.fn()},
      createDataChannel(){return this.channel;}};
    function RTC(){return peer;}
    vi.stubGlobal('window',{RTCPeerConnection:RTC});vi.stubGlobal('RTCPeerConnection',RTC);
    vi.stubGlobal('navigator',{mediaDevices:{getUserMedia:vi.fn(async()=>media)}});
    vi.stubGlobal('MediaStream',function(){return media;});
    callbacks={status:vi.fn(),caption:vi.fn(),reply:vi.fn(),error:vi.fn(),session:vi.fn()};
    audio={play:vi.fn(async()=>{}),pause:vi.fn(),srcObject:null};
  });
  afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();});

  it('does not ask for a microphone when disabled',async()=>{
    vi.mocked(api).mockResolvedValueOnce({enabled:false});
    await new VoiceClient(callbacks,audio).start(selection);
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
    expect(callbacks.error).toHaveBeenCalledWith('voice_unavailable');
    expect(api).toHaveBeenCalledTimes(1);
  });

  it('accepts replies only from the authenticated server and closes both paths',async()=>{
    const reply={text:'Verified',conversation:{id:'owned'}};
    vi.mocked(api).mockImplementation(async(path)=>path==='/voice/capabilities'?{enabled:true}:
      path==='/voice/sessions'?{id:'session',conversationId:'owned',sdp:'answer',expiresAt:Date.now()/1000+300}:
      path.endsWith('/heartbeat')?{revision:1,reply,status:'active'}:{status:'closed'});
    const client=new VoiceClient(callbacks,audio);await client.start(selection);
    expect(callbacks.session).toHaveBeenCalledWith('owned');expect(callbacks.reply).toHaveBeenCalledWith(reply);
    peer.channel.onmessage({data:JSON.stringify({type:'response.event',event:{type:'function_call',name:'transfer_money'}})});
    expect(callbacks.reply).toHaveBeenCalledTimes(1);
    client.mute(true);expect(track.enabled).toBe(false);client.mute(false);expect(track.enabled).toBe(true);
    await client.stop();expect(track.stop).toHaveBeenCalled();expect(peer.close).toHaveBeenCalled();
    expect(peer.channel.send).toHaveBeenCalledWith(JSON.stringify({type:'session.close'}));
    expect(api).toHaveBeenCalledWith('/voice/sessions/session/close','POST',{});
    expect(vi.getTimerCount()).toBe(0);
  });

  it('releases a microphone granted after the user cancelled',async()=>{
    vi.mocked(api).mockResolvedValue({enabled:true});
    let grant!:(stream:any)=>void;
    vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementation(()=>new Promise(resolve=>{grant=resolve;}));
    const client=new VoiceClient(callbacks,audio);const start=client.start(selection);await Promise.resolve();
    await client.stop();grant(media);await start;
    expect(track.stop).toHaveBeenCalled();expect(peer.createOffer).not.toHaveBeenCalled();
  });
});
