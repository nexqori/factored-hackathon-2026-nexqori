let csrfToken = '';
export function setCsrf(token: string) { csrfToken = token; }
export class ApiError extends Error { constructor(public code: string, public status: number) { super(code); } }
export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try { response = await fetch('/api' + path, { method, signal, credentials: 'same-origin', headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }); }
  catch (error) { if (signal?.aborted) throw error; throw new ApiError('network', 0); }
  const data = await response.json().catch(() => ({}));
  // Cancellation can happen after headers arrive, while the JSON body is read.
  // Never deliver an empty/stale payload to a component whose filter has changed.
  signal?.throwIfAborted();
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('nexqori-session-ended'));
    throw new ApiError(data.error || 'generic', response.status);
  }
  return data as T;
}
