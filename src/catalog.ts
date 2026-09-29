import registry from '../backend/service_catalog.json';
import type { Locale } from './i18n';
import type { Service, ServiceItem } from './types';

export const catalogIds = new Set(registry.items.map(item => item.id));
export function serviceTitle(id: string, locale: Locale): string {
  return registry.items.find(item => item.id === id)?.copy[locale].title || id;
}
export function serviceCategory(id: string): Service | undefined {
  return registry.items.find(item => item.id === id)?.category as Service | undefined;
}
export function localService(id: string, locale: Locale): ServiceItem | undefined {
  const item = registry.items.find(item => item.id === id);
  if (!item) return undefined;
  return { ...item, ...item.copy[locale] } as ServiceItem;
}
export function parseAmount(value: string): number | null {
  const input = value.trim();
  if (!/^\d{1,7}([.,]\d{1,2})?$/.test(input)) return null;
  const [whole, fraction = ''] = input.replace(',', '.').split('.');
  const minor = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(minor) && minor > 0 && minor <= 100000000 ? minor : null;
}
