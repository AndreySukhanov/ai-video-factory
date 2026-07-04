'use client';

import { display } from '@/lib/fonts';

interface PageHeaderProps {
    /** Mono eyebrow label above the title (uppercase, tracked) */
    label: string;
    title: string;
    subtitle?: string;
    actions?: React.ReactNode;
}

/** Shared page header in the production-line style of the landing. */
export default function PageHeader({ label, title, subtitle, actions }: PageHeaderProps) {
    return (
        <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
            <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-[var(--brand-1)] mb-2">
                    ● {label}
                </div>
                <h1 className={`${display.className} text-2xl sm:text-3xl font-bold text-white leading-tight`}>
                    {title}
                </h1>
                {subtitle && <p className="text-sm text-[var(--muted)] mt-1.5 max-w-xl">{subtitle}</p>}
            </div>
            {actions && <div className="flex items-center gap-3 shrink-0">{actions}</div>}
        </div>
    );
}
