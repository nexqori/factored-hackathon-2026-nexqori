import { describe, it, expect } from 'vitest';
import { parseAmount, serviceTitle } from './catalog';
import { currentDestination, safeNavigation } from './navigation';

describe('Service requests', () => {
  it('parses exact minor units and refuses ambiguous or invalid amounts', () => {
    expect(parseAmount('459.90')).toBe(45990);
    expect(parseAmount('459,9')).toBe(45990);
    expect(parseAmount('0.01')).toBe(1);
    expect(parseAmount('1000000')).toBe(100000000);
    for (const value of ['', '0', '-12', '12.345', '1,000.00', '1e4', 'NaN', '1000000.01']) expect(parseAmount(value)).toBeNull();
  });
  it('opens only a registered service route and preserves safe context', () => {
    const command = { tool: 'navigate_in_app', destination: 'services', serviceId: 'phone-bill', route: '/services/catalog/phone-bill' };
    expect(safeNavigation(command)).toBe(command.route);
    expect(safeNavigation({ ...command, route: 'https://example.com' })).toBeNull();
    expect(safeNavigation({ ...command, serviceId: '../../admin' })).toBeNull();
    expect(safeNavigation({ ...command, destination: 'payments' })).toBeNull();
    expect(currentDestination('/services/catalog/phone-bill', '')).toBe('payments');
    expect(currentDestination('/services/catalog/app-support', '')).toBe('services');
    expect(serviceTitle('phone-bill', 'en')).toBe('Pay a phone bill');
  });
});
