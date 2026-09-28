import { describe, it, expect } from 'vitest';
import es from './locales/es.json';
import en from './locales/en.json';
import pt from './locales/pt.json';
const dictionaries = { es, en, pt };
describe('Three-language interface contract', () => {
  for (const [locale, dictionary] of Object.entries(dictionaries)) {
    it(locale + ' includes every key and interpolation variable', () => {
      expect(Object.keys(dictionary).sort()).toEqual(Object.keys(es).sort());
      for (const key of Object.keys(es) as (keyof typeof es)[]) {
        expect(dictionary[key].trim().length).toBeGreaterThan(0);
        expect(dictionary[key].match(/{{[^}]+}}/g) || []).toEqual(es[key].match(/{{[^}]+}}/g) || []);
      }
    });
  }
});
const luminance = (hex: string) => {
  const parts = hex.replace('#', '').match(/../g)!.map(v => parseInt(v, 16) / 255).map(v => v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4));
  return .2126 * parts[0] + .7152 * parts[1] + .0722 * parts[2];
};
describe('Brand reading contrast', () => {
  for (const pair of [['#9A4B32', '#FFFCF9'], ['#392C27', '#F2D8C8'], ['#76645B', '#FFFCF9']]) {
    it(pair.join(' on ') + ' meets normal-text AA contrast', () => {
      const [a, b] = pair.map(luminance).sort((x, y) => y - x);
      expect((a + .05) / (b + .05)).toBeGreaterThanOrEqual(4.5);
    });
  }
});
