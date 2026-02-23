'use client';

import Link from 'next/link';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface RouteErrorStateProps {
  title?: string;
  description?: string;
  onRetry: () => void;
  homeHref?: string;
}

export default function RouteErrorState({
  title = 'Something went wrong',
  description = 'The page crashed while processing data. You can retry or return home.',
  onRetry,
  homeHref = '/',
}: RouteErrorStateProps) {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-gray-800/70 border border-red-500/30 rounded-2xl p-6">
        <div className="flex items-start gap-3 mb-4">
          <AlertTriangle className="w-6 h-6 text-red-400 mt-0.5" />
          <div>
            <h1 className="text-xl font-semibold">{title}</h1>
            <p className="text-gray-300 text-sm mt-1">{description}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
          <Link
            href={homeHref}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  );
}
