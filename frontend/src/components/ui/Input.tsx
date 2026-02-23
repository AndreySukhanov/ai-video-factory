import { forwardRef, InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

type InputProps = InputHTMLAttributes<HTMLInputElement>;

const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] px-3 text-sm text-white',
        'placeholder:text-[var(--muted)]/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60',
        className,
      )}
      {...props}
    />
  );
});

export default Input;
