import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import es from './locales/es.json';
import en from './locales/en.json';
import pt from './locales/pt.json';
export const locales = ['es', 'en', 'pt'] as const;
export type Locale = typeof locales[number];
export const isLocale = (value: string): value is Locale => locales.includes(value as Locale);
export const localeTags = { es: 'es-MX', en: 'en-US', pt: 'pt-BR' };
let initial: Locale = 'es';
try { const stored = localStorage.getItem('nexqori-language'); const browser = navigator.language.split('-')[0]; initial = stored && isLocale(stored) ? stored : isLocale(browser) ? browser : 'es'; } catch { /* Browser storage is optional. */ }
void i18n.use(initReactI18next).init({ resources: { es: { translation: es }, en: { translation: en }, pt: { translation: pt } }, lng: initial, fallbackLng: 'es', supportedLngs: [...locales], keySeparator: false, interpolation: { escapeValue: false } });
i18n.on('languageChanged', lng => { document.documentElement.lang = lng; document.title = 'Nexqori · ' + i18n.t('tagline'); try { localStorage.setItem('nexqori-language', lng); } catch { /* Preferences still work in memory. */ } });
document.documentElement.lang = initial;
document.title = 'Nexqori · ' + i18n.t('tagline');
export default i18n;
