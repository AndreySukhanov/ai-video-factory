import { cn } from '@/lib/utils';

interface ProgressBarProps {
  value: number;
  className?: string;
  showValue?: boolean;
}

export default function ProgressBar({ value, className, showValue = false }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn('w-full', className)}>
      <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-[var(--brand-1)] to-[var(--brand-2)] transition-all duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showValue && <div className="mt-1 text-right text-xs text-[var(--muted)]">{Math.round(clamped)}%</div>}
    </div>
  );
}
