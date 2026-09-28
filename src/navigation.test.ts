import { describe, expect, it } from 'vitest';
import { currentDestination, safeNavigation } from './navigation';

describe('Agent navigation boundary', () => {
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
});
