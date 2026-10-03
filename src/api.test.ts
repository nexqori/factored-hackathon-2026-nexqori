import { afterEach, expect, it, vi } from 'vitest';
import { api } from './api';

afterEach(() => vi.unstubAllGlobals());

it('rejects a response cancelled while its JSON body is being read', async () => {
  const controller = new AbortController();
  const body = vi.fn(async () => {
    controller.abort();
    throw controller.signal.reason;
  });
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: body })));
  await expect(api('/admin/audit', 'GET', undefined, controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(body).toHaveBeenCalledOnce();
});

it('does not deliver stale audit rows if cancellation happens before the body resolves', async () => {
  const controller = new AbortController();
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => {
    controller.abort();
    return { events: [{ id: 'old-filter-event' }], actions: [], nextOffset: null };
  } })));
  await expect(api('/admin/audit', 'GET', undefined, controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
});
