import { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'muted';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-[var(--brand-1)]/15 text-[var(--brand-1)] border-[var(--brand-1)]/30',
  success: 'bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30',
  warning: 'bg-[var(--brand-2)]/15 text-[var(--brand-2)] border-[var(--brand-2)]/30',
  danger: 'bg-[var(--danger)]/15 text-[var(--danger)] border-[var(--danger)]/30',
  muted: 'bg-white/5 text-[var(--muted)] border-white/10',
};

export default function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
