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

export async function downloadDocument(id: string, filename: string): Promise<void> {
  let response: Response;
  try { response = await fetch('/api/documents/' + encodeURIComponent(id), {credentials:'same-origin'}); }
  catch { throw new ApiError('network', 0); }
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('nexqori-session-ended'));
    const body = await response.json().catch(()=>({})); throw new ApiError(body.error || 'generic', response.status);
  }
  const blob = await response.blob(); const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href=url; a.download=filename; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
