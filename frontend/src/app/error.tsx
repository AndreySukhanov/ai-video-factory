'use client';

import { useEffect } from 'react';
import RouteErrorState from '@/components/RouteErrorState';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[UI] Route error boundary caught:', error);
  }, [error]);

  return (
    <RouteErrorState
      title="Application error"
      description="A runtime error occurred while rendering this page."
      onRetry={reset}
    />
  );
}
