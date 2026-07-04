import { Unbounded } from 'next/font/google';

// Display font of the app (landing hero, page titles, wordmark).
// Loaded once here so every page shares the same instance.
export const display = Unbounded({
  subsets: ['latin', 'cyrillic'],
  weight: ['500', '700', '900'],
  display: 'swap',
});
