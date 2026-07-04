const rawApiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').trim();

function stripTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

function normalizeApiOrigin(value: string): string {
  const withoutTrailing = stripTrailingSlashes(value);
  if (withoutTrailing.endsWith('/api/v1')) {
    return withoutTrailing.slice(0, -('/api/v1'.length));
  }
  return withoutTrailing;
}

export const API_BASE_URL = normalizeApiOrigin(rawApiBaseUrl);
export const API_V1_BASE_URL = `${API_BASE_URL}/api/v1`;
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

// If the backend is protected with API_AUTH_KEY, the key is provided via
// NEXT_PUBLIC_API_KEY and sent with every request as the X-API-Key header.
// Empty = the header is not sent.
const apiKey = (process.env.NEXT_PUBLIC_API_KEY || '').trim();
export const API_AUTH_HEADERS: Record<string, string> = apiKey ? { 'X-API-Key': apiKey } : {};

// Fetch wrapper for direct API calls from pages: adds the X-API-Key header.
export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: { ...API_AUTH_HEADERS, ...(init?.headers || {}) },
  });
}

