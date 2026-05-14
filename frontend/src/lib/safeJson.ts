export function safeJsonParse<T>(value: string | null | undefined, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function safeStringArray(value: string | null | undefined): string[] {
  const parsed = safeJsonParse<unknown>(value, []);
  if (!Array.isArray(parsed)) return [];
  return parsed.filter((item): item is string => typeof item === "string");
}

export function safeArray<T>(
  value: string | null | undefined,
  isItem: (item: unknown) => item is T,
): T[] {
  const parsed = safeJsonParse<unknown>(value, []);
  if (!Array.isArray(parsed)) return [];
  return parsed.filter(isItem);
}
