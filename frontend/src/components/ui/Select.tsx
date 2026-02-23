import { forwardRef, SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>;

const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select
      ref={ref}
      className={cn(
        'h-10 w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] px-3 text-sm text-white',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
});

export default Select;
