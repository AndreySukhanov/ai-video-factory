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

// Если бэкенд защищён API_AUTH_KEY, ключ прокидывается через NEXT_PUBLIC_API_KEY
// и уходит в каждый запрос заголовком X-API-Key. Пусто = заголовок не шлём.
const apiKey = (process.env.NEXT_PUBLIC_API_KEY || '').trim();
export const API_AUTH_HEADERS: Record<string, string> = apiKey ? { 'X-API-Key': apiKey } : {};

// Обёртка над fetch для прямых вызовов API со страниц: добавляет X-API-Key.
export function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  return fetch(input, {
    ...init,
    headers: { ...API_AUTH_HEADERS, ...(init?.headers || {}) },
  });
}

