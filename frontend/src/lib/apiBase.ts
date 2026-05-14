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

