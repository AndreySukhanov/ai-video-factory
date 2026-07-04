'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
    TrendingUp, Video, ClipboardList, Youtube, BarChart3, Home, Zap
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { API_V1_BASE_URL, apiFetch } from '@/lib/apiBase';
import { display } from '@/lib/fonts';

interface SidebarItemProps {
    href: string;
    icon: React.ReactNode;
    label: string;
    badge?: number;
    iconColor?: string;
    isActive: boolean;
}

function SidebarItem({ href, icon, label, badge, isActive }: SidebarItemProps) {
    return (
        <Link
            href={href}
            className={`relative flex items-center gap-3 px-3 py-2 rounded-[var(--radius-sm)] text-sm font-medium transition-colors group border ${
                isActive
                    ? 'bg-[var(--surface-2)]/80 text-white border-[var(--brand-1)]/30'
                    : 'text-[var(--muted)] border-transparent hover:text-white hover:bg-white/[0.04]'
            }`}
        >
            {isActive && (
                <span aria-hidden className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-[var(--brand-1)] rounded-full" />
            )}
            <span className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? 'text-[var(--brand-1)]' : 'text-[var(--muted)] group-hover:text-[var(--brand-1)]'}`}>
                {icon}
            </span>
            <span className="flex-1">{label}</span>
            {badge != null && badge > 0 && (
                <span className="bg-[var(--brand-2)] text-[#2a1802] text-[10px] font-bold rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
                    {badge > 99 ? '99+' : badge}
                </span>
            )}
        </Link>
    );
}

function SidebarSection({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="mb-5">
            <div className="px-3 mb-1.5 font-mono text-[9px] text-[var(--muted)]/70 uppercase tracking-[0.3em]">
                {label}
            </div>
            <div className="space-y-0.5">
                {children}
            </div>
        </div>
    );
}

export default function Sidebar() {
    const pathname = usePathname();
    const { t } = useLanguage();
    const [newTrendsCount, setNewTrendsCount] = useState(0);

    // Count new trends since last visit
    useEffect(() => {
        const fetchAndCount = async () => {
            try {
                const lastVisited = localStorage.getItem('sidebar_last_visited_trends');
                const res = await apiFetch(`${API_V1_BASE_URL}/trends/?limit=50`);
                if (!res.ok) return;
                const trends = await res.json();
                if (lastVisited && Array.isArray(trends)) {
                    const count = trends.filter((t: { fetched_at?: string }) =>
                        t.fetched_at && t.fetched_at > lastVisited
                    ).length;
                    setNewTrendsCount(count);
                }
            } catch {
                // silently fail
            }
        };
        fetchAndCount();
    }, []);

    // Clear badge when visiting trends page (setState during render — React's
    // documented pattern for adjusting state on prop change)
    const [prevPathname, setPrevPathname] = useState(pathname);
    if (prevPathname !== pathname) {
        setPrevPathname(pathname);
        if (pathname === '/trends') setNewTrendsCount(0);
    }

    // Remember the visit so the badge stays cleared on next mount
    useEffect(() => {
        if (pathname === '/trends') {
            localStorage.setItem('sidebar_last_visited_trends', new Date().toISOString());
        }
    }, [pathname]);

    // Don't render on home / landing page
    if (pathname === '/') return null;

    return (
        <aside className="w-52 shrink-0 bg-[var(--surface-1)]/60 border-r border-white/[0.06] flex flex-col min-h-screen sticky top-0 h-screen overflow-y-auto">
            {/* Logo */}
            <div className="px-4 py-5 border-b border-white/[0.06]">
                <Link href="/" className="flex items-center gap-2 text-white hover:opacity-80 transition-opacity">
                    <Zap className="w-4 h-4 text-[var(--brand-1)]" />
                    <span className={`${display.className} text-[11px] font-bold tracking-wide`}>AI VIDEO FACTORY</span>
                </Link>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-4">
                <SidebarSection label={t('sidebar.content')}>
                    <SidebarItem
                        href="/trends"
                        icon={<TrendingUp className="w-4 h-4" />}
                        label={t('sidebar.trends')}
                        badge={newTrendsCount}
                        iconColor="text-red-400"
                        isActive={pathname === '/trends'}
                    />
                    <SidebarItem
                        href="/generate"
                        icon={<Video className="w-4 h-4" />}
                        label={t('sidebar.generate')}
                        iconColor="text-teal-400"
                        isActive={pathname === '/generate' || pathname.startsWith('/generate/')}
                    />
                    <SidebarItem
                        href="/review"
                        icon={<ClipboardList className="w-4 h-4" />}
                        label={t('sidebar.review')}
                        iconColor="text-orange-400"
                        isActive={pathname === '/review'}
                    />
                </SidebarSection>

                <SidebarSection label={t('sidebar.publish')}>
                    <SidebarItem
                        href="/youtube"
                        icon={<Youtube className="w-4 h-4" />}
                        label={t('sidebar.youtube')}
                        iconColor="text-red-500"
                        isActive={pathname === '/youtube'}
                    />
                    <SidebarItem
                        href="/dashboard"
                        icon={<BarChart3 className="w-4 h-4" />}
                        label={t('sidebar.dashboard')}
                        iconColor="text-blue-400"
                        isActive={pathname === '/dashboard'}
                    />
                </SidebarSection>
            </nav>

            {/* Footer */}
            <div className="px-4 py-4 border-t border-white/[0.06]">
                <Link href="/" className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]/70 hover:text-[var(--brand-1)] transition-colors">
                    <Home className="w-3.5 h-3.5" />
                    {t('sidebar.home')}
                </Link>
            </div>
        </aside>
    );
}
