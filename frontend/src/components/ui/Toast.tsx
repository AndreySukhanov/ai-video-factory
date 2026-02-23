import { ComponentType } from 'react';
import { AlertCircle, CheckCircle2, Info, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

type ToastKind = 'info' | 'success' | 'warning' | 'error';

interface ToastProps {
  title: string;
  message?: string;
  kind?: ToastKind;
  className?: string;
}

const kindMap: Record<ToastKind, { border: string; icon: ComponentType<{ className?: string }> }> = {
  info: { border: 'border-cyan-400/40', icon: Info },
  success: { border: 'border-green-400/40', icon: CheckCircle2 },
  warning: { border: 'border-amber-400/40', icon: AlertCircle },
  error: { border: 'border-red-400/40', icon: XCircle },
};

export default function Toast({ title, message, kind = 'info', className }: ToastProps) {
  const Icon = kindMap[kind].icon;
  return (
    <div
      role="status"
      className={cn(
        'rounded-[var(--radius-md)] border bg-[var(--surface-2)]/95 p-3 text-sm text-white shadow-[var(--shadow-soft)]',
        kindMap[kind].border,
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4" />
        <div>
          <div className="font-medium">{title}</div>
          {message && <div className="text-[var(--muted)] mt-0.5">{message}</div>}
        </div>
      </div>
    </div>
  );
}
