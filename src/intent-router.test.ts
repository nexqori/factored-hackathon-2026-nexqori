import { describe, expect, it, vi } from 'vitest';
import { intentDestinations, isRoutedIntent, navigateForIntent } from './intent-router';

describe('intent routing', () => {
  it('maps transactions, requests, claims and cards to existing destinations', () => {
    expect(intentDestinations).toEqual({
      movements: 'movements',
      requests: 'requests',
      report: 'requests',
      cards: 'cards',
    });
  });

  it('navigates to the allowlisted route for a recognized intent', async () => {
    const navigate = vi.fn();
    const onError = vi.fn();

    const routes = [
      ['movements', '/movements'],
      ['requests', '/requests'],
      ['report', '/requests'],
      ['cards', '/products?kind=cards'],
    ] as const;

    for (const [intent, route] of routes) {
      expect(isRoutedIntent(intent)).toBe(true);
      await expect(navigateForIntent(intent, navigate, onError)).resolves.toBe(true);
      expect(navigate).toHaveBeenLastCalledWith(route);
    }

    expect(navigate).toHaveBeenCalledTimes(routes.length);
    expect(onError).not.toHaveBeenCalled();
  });

  it('contains navigation failures and reports them to the caller', async () => {
    const error = new Error('Navigation failed');
    const navigate = vi.fn().mockRejectedValue(error);
    const onError = vi.fn();

    await expect(navigateForIntent('cards', navigate, onError)).resolves.toBe(false);
    expect(onError).toHaveBeenCalledWith(error);
  });

  it('rejects unknown intents without navigating and reports the error', async () => {
    const navigate = vi.fn();
    const onError = vi.fn();

    expect(isRoutedIntent('unknown-intent')).toBe(false);
    await expect(navigateForIntent('unknown-intent', navigate, onError)).resolves.toBe(false);
    expect(navigate).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.any(Error));
  });
});
