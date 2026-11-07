import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-200 text-sm"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-rose-400" aria-hidden="true" />
        <span>{message}</span>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-rose-400/40 hover:bg-rose-500/20 text-xs font-semibold transition self-start sm:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Retry
        </button>
      )}
    </div>
  );
}
