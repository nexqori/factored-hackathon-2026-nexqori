import {describe,it,expect} from 'vitest';
import es from './locales/es.json';import en from './locales/en.json';import pt from './locales/pt.json';
describe('localization contract',()=>{it('has equal nonempty ES/EN/PT coverage',()=>{for(const dict of [en,pt]){expect(Object.keys(dict).sort()).toEqual(Object.keys(es).sort());expect(Object.values(dict).every(v=>typeof v==='string'&&v.length>0)).toBe(true)}})});
