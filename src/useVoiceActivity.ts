import {useEffect,useState,type RefObject} from 'react';

/** Observe only the received audio. This neither captures nor stores audio. */
export function useVoiceActivity(audio:RefObject<HTMLAudioElement|null>,active:boolean){
  const [level,setLevel]=useState(0);
  useEffect(()=>{
    const element=audio.current;
    if(!active||!element){setLevel(0);return;}
    let context:AudioContext|null=null;
    let source:MediaStreamAudioSourceNode|null=null;
    let analyser:AnalyserNode|null=null;
    let frame=0,lastSignal=-Infinity,lastSample=0;
    function reset(){
      cancelAnimationFrame(frame);
      source?.disconnect();analyser?.disconnect();
      if(context)void context.close().catch(()=>{});
      context=null;source=null;analyser=null;lastSignal=-Infinity;
      setLevel(0);
    }
    function start(){
      if(context||!element?.srcObject||!window.AudioContext)return;
      try{
        context=new AudioContext();
        source=context.createMediaStreamSource(element.srcObject as MediaStream);
        analyser=context.createAnalyser();analyser.fftSize=256;
        // No connection to the speakers: the audio element already plays the track.
        source.connect(analyser);
        void context.resume().catch(()=>{});
        const samples=new Float32Array(analyser.fftSize);
        function sample(now:number){
          if(!analyser||!context||!element)return;
          if(now-lastSample>=60){
            lastSample=now;
            analyser.getFloatTimeDomainData(samples);
            const rms=Math.sqrt(samples.reduce((sum,value)=>sum+value*value,0)/samples.length);
            const audible=context.state==='running'&&!element.muted&&element.volume>0;
            if(audible&&rms>0.012)lastSignal=now;
            const next=audible&&now-lastSignal<350?Math.max(.12,Math.min(1,rms*7)):0;
            setLevel(Math.round(next*20)/20);
          }
          frame=requestAnimationFrame(sample);
        }
        frame=requestAnimationFrame(sample);
      }catch{reset();} // Unsupported audio analysis must not interrupt the call.
    }
    element.addEventListener('playing',start);
    element.addEventListener('pause',reset);
    element.addEventListener('emptied',reset);
    element.addEventListener('ended',reset);
    if(!element.paused)start();
    return()=>{
      element.removeEventListener('playing',start);
      element.removeEventListener('pause',reset);
      element.removeEventListener('emptied',reset);
      element.removeEventListener('ended',reset);
      reset();
    };
  },[audio,active]);
  return active?level:0;
}
