import { useEffect, useId, useRef, useState } from 'react';
import { Check, ChevronDown, Globe2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { locales, type Locale } from './i18n';

export const languageLabels = { es: 'Español', en: 'English', pt: 'Português' };
const names = languageLabels;
export function LanguagePicker({ onChange }: { onChange: (locale: Locale) => void }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const id = useId();
  const selected = i18n.language as Locale;
  function close() { setOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  return <div className="language-picker" ref={root} onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false); }} onKeyDown={event => {
    if (event.key === 'Escape' && open) { event.preventDefault(); close(); }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      if (!open) { setOpen(true); return; }
      const choices = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')];
      const index = choices.indexOf(document.activeElement as HTMLButtonElement);
      choices[event.key === 'Home' ? 0 : event.key === 'End' ? choices.length - 1 : (index + (event.key === 'ArrowUp' ? -1 : 1) + choices.length) % choices.length]?.focus();
    }
  }}>
    <button className="language-trigger" ref={trigger} aria-label={t('language')} aria-haspopup="menu" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}><Globe2 size={17} /><span>{names[selected]}</span><ChevronDown size={15} /></button>
    {open && <div className="language-menu" role="menu" aria-label={t('language')} id={id}><p aria-hidden="true">{t('chooseLanguage')}</p>{locales.map(locale => <button key={locale} type="button" role="menuitemradio" aria-checked={locale === selected} lang={locale} data-locale={locale} onClick={() => { onChange(locale); close(); }}><span className="language-code" aria-hidden="true">{locale.toUpperCase()}</span><span>{names[locale]}</span>{locale === selected && <Check size={17} />}</button>)}</div>}
  </div>;
}
