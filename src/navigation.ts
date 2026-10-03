// Keep this allowlist aligned with backend/navigation.py. Never execute a URL from chat.
import { catalogIds, serviceCategory } from './catalog';
export const destinations = {
  home: '/', products: '/products', movements: '/movements', requests: '/requests', complaints: '/complaints', documents: '/documents',
  services: '/services', help: '/help', accounts: '/products?kind=accounts', cards: '/cards',
  transfers: '/services/transfers', payments: '/services/payments', loans: '/services/loans',
  investments: '/services/investments', insurance: '/services/insurance', cash: '/services/cash', settings: '/settings',
} as const;
export type Destination = keyof typeof destinations;
export type NavigationCommand = { tool: 'navigate_in_app'; destination: Destination; route: string; serviceId?: string; filters?: {start?:string;end?:string;product?:string} };
export function safeNavigation(command: unknown): string | null {
  if (!command || typeof command !== 'object') return null;
  const c = command as Partial<NavigationCommand>;
  if (c.tool !== 'navigate_in_app' || !c.destination || !Object.hasOwn(destinations, c.destination)) return null;
  if(c.filters!==undefined){
    const f=c.filters;
    if(c.destination!=='movements'||c.serviceId!==undefined||!f||typeof f!=='object'||!Object.keys(f).length||Object.keys(f).some(k=>!['start','end','product'].includes(k)))return null;
    if(Boolean(f.start)!==Boolean(f.end))return null;
    if(f.start||f.end){
      if(!validDate(f.start)||!validDate(f.end)||f.start!>f.end!||(Date.parse(f.end!)-Date.parse(f.start!))/86400000>366)return null;
    }
    if(f.product!==undefined&&(typeof f.product!=='string'||! /^[A-Za-z0-9_-]{1,64}$/.test(f.product)))return null;
    const params=new URLSearchParams();for(const key of ['start','end','product'] as const)if(f[key]!==undefined)params.set(key,f[key]!);
    const route='/movements?'+params.toString();return c.route===route?route:null;
  }
  if (c.serviceId !== undefined) {
    return c.destination === 'services' && typeof c.serviceId === 'string' && catalogIds.has(c.serviceId) && c.route === '/services/catalog/' + c.serviceId ? c.route : null;
  }
  // An idempotent replay can contain the former cards route. Normalize only
  // this exact known route so existing saved turns activate the Cards menu too.
  if (c.destination === 'cards' && c.route === '/products?kind=cards') return destinations.cards;
  return destinations[c.destination] === c.route ? c.route : null;
}
export function validDate(value:unknown):value is string{return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;}

// A response may have no navigation. A supplied command must match the server
// allowlist, and a rejected router transition must not become an unhandled promise.
export async function navigateWithCommand(
  command: unknown,
  navigate: (route: string) => void | Promise<void>,
  onError: (error: unknown) => void,
): Promise<boolean> {
  if (command == null) return false;
  try {
    const route = safeNavigation(command);
    if (!route) throw new Error('Unsupported navigation command');
    await navigate(route);
    return true;
  } catch (error) {
    onError(error);
    return false;
  }
}

export function currentDestination(pathname: string, search: string): Destination {
  if (pathname.startsWith('/services/catalog/')) { const category = serviceCategory(pathname.slice('/services/catalog/'.length)); return category && Object.hasOwn(destinations, category) ? category as Destination : 'services'; }
  if (pathname === '/cards') return 'cards';
  const kind = new URLSearchParams(search).get('kind');
  if (pathname === '/products' && (kind === 'accounts' || kind === 'cards')) return kind;
  return (Object.entries(destinations).find(([, path]) => path === pathname)?.[0] as Destination) || 'home';
}
