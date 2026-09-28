// Keep this allowlist aligned with backend/navigation.py. Never execute a URL from chat.
export const destinations = {
  home: '/', products: '/products', movements: '/movements', requests: '/requests',
  services: '/services', help: '/help', accounts: '/products?kind=accounts', cards: '/products?kind=cards',
  transfers: '/services/transfers', payments: '/services/payments', loans: '/services/loans',
  investments: '/services/investments', insurance: '/services/insurance', cash: '/services/cash',
} as const;
export type Destination = keyof typeof destinations;
export type NavigationCommand = { tool: 'navigate_in_app'; destination: Destination; route: string };
export function safeNavigation(command: unknown): string | null {
  if (!command || typeof command !== 'object') return null;
  const c = command as Partial<NavigationCommand>;
  if (c.tool !== 'navigate_in_app' || !c.destination || !Object.hasOwn(destinations, c.destination)) return null;
  return destinations[c.destination] === c.route ? c.route : null;
}
export function currentDestination(pathname: string, search: string): Destination {
  const kind = new URLSearchParams(search).get('kind');
  if (pathname === '/products' && (kind === 'accounts' || kind === 'cards')) return kind;
  return (Object.entries(destinations).find(([, path]) => path === pathname)?.[0] as Destination) || 'home';
}
