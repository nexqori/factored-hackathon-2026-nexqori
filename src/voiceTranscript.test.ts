import {describe,expect,it} from 'vitest';
import {groupVoiceTranscript,type VoiceFragment} from './voiceTranscript';
const fragment=(id:string,speaker:'user'|'assistant',text:string,startMs:number):VoiceFragment=>({id,speaker,text,startMs,endMs:startMs+100});
describe('voice transcript',()=>{
  it('orders delayed fragments by provider timing and keeps both speakers',()=>{
    const fragments=[fragment('1','user','No reconozco',100),fragment('2','assistant','Lo revisamos.',500),fragment('3','user',' este cargo.',200),fragment('4','user','Sí, ese.',900)];
    expect(groupVoiceTranscript(fragments).map(r=>[r.speaker,r.text])).toEqual([
      ['user','No reconozco este cargo.'],['assistant','Lo revisamos.'],['user','Sí, ese.']]);
    expect(fragments[0].text).toBe('No reconozco');
  });
  it('preserves repeated words and breaks long pauses',()=>{
    expect(groupVoiceTranscript([fragment('1','user','no ',0),fragment('2','user','no',100),fragment('3','user','Otro tema',4000)]).map(r=>r.text)).toEqual(['no no','Otro tema']);
  });
});
