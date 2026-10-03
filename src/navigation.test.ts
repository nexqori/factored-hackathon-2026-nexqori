import { describe, expect, it, vi } from 'vitest';
import { currentDestination, navigateWithCommand, safeNavigation } from './navigation';

describe('Agent navigation boundary', () => {
  it('validates movement filters and their exact route without accepting extra parameters',()=>{
    const command={tool:'navigate_in_app',destination:'movements',filters:{start:'2026-09-01',end:'2026-09-30',product:'account-01'},route:'/movements?start=2026-09-01&end=2026-09-30&product=account-01'};
    expect(safeNavigation(command)).toBe(command.route);
    for(const filters of [{...command.filters,start:'2026-02-30'}, {...command.filters,end:'2024-01-01'}, {...command.filters,owner:'other'}, {start:'2026-09-01'}, {product:'../admin'}, {}])expect(safeNavigation({...command,filters})).toBeNull();
    expect(safeNavigation({...command,route:command.route+'&action=pay'})).toBeNull();
    expect(safeNavigation({...command,destination:'requests'})).toBeNull();
  });
  it('opens a permitted destination and rejects arbitrary, mismatched or inherited routes', () => {
    expect(safeNavigation({ tool: 'navigate_in_app', destination: 'cards', route: '/products?kind=cards' })).toBe('/products?kind=cards');
    for (const command of [null, {}, { tool: 'navigate_in_app', destination: 'cards', route: 'https://example.com' },
      { tool: 'navigate_in_app', destination: 'admin', route: '/admin' },
      { tool: 'navigate_in_app', destination: '__proto__', route: '/' },
      { tool: 'execute_payment', destination: 'payments', route: '/services/payments' }]) {
      expect(safeNavigation(command)).toBeNull();
    }
  });
  it('sends only a known page identifier as context', () => {
    expect(currentDestination('/products', '?kind=cards')).toBe('cards');
    expect(currentDestination('/services/transfers', '')).toBe('transfers');
    expect(currentDestination('/admin', '')).toBe('home');
    expect(currentDestination('/products', '?kind=https://example.com')).toBe('products');
  });
  it('ignores an absent command and rejects invalid commands without navigating', async () => {
    const navigate = vi.fn(); const onError = vi.fn();
    for (const command of [null, undefined]) await expect(navigateWithCommand(command, navigate, onError)).resolves.toBe(false);
    expect(onError).not.toHaveBeenCalled();
    for (const command of [{ tool:'navigate_in_app', destination:'admin', route:'/admin' },
      { tool:'navigate_in_app', destination:'cards', route:'https://example.com' },
      { tool:'navigate_in_app', destination:'services', serviceId:'phone-bill', route:'/services/catalog/internet-bill' }]) {
      await expect(navigateWithCommand(command, navigate, onError)).resolves.toBe(false);
    }
    expect(navigate).not.toHaveBeenCalled(); expect(onError).toHaveBeenCalledTimes(3);
  });
  it('keeps requests, complaints and service forms on their own allowed routes', async () => {
    const navigate = vi.fn(); const onError = vi.fn();
    for (const destination of ['movements', 'requests', 'complaints'] as const) {
      await expect(navigateWithCommand({tool:'navigate_in_app',destination,route:'/'+destination},navigate,onError)).resolves.toBe(true);
      expect(navigate).toHaveBeenLastCalledWith('/'+destination);
    }
    await expect(navigateWithCommand({tool:'navigate_in_app',destination:'services',serviceId:'phone-bill',route:'/services/catalog/phone-bill'},navigate,onError)).resolves.toBe(true);
    expect(navigate).toHaveBeenLastCalledWith('/services/catalog/phone-bill'); expect(onError).not.toHaveBeenCalled();
  });
  it('waits for a successful transition and reports both synchronous and asynchronous failures', async () => {
    const command = {tool:'navigate_in_app',destination:'cards',route:'/products?kind=cards'};
    const onError = vi.fn(); const failure = new Error('Navigation failed');
    for (const navigate of [vi.fn(() => {throw failure;}), vi.fn().mockRejectedValue(failure)]) {
      await expect(navigateWithCommand(command,navigate,onError)).resolves.toBe(false);
      expect(onError).toHaveBeenLastCalledWith(failure);
    }
    let finish: () => void = () => {};
    const pending = new Promise<void>(resolve => {finish=resolve;}); const observed=vi.fn();
    const completion=navigateWithCommand(command,()=>pending,onError).then(observed);
    await Promise.resolve(); expect(observed).not.toHaveBeenCalled();
    finish(); await completion; expect(observed).toHaveBeenCalledWith(true); expect(onError).toHaveBeenCalledTimes(2);
  });
});
