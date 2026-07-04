'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Unbounded } from 'next/font/google';
import {
  Play, TrendingUp, PenLine, Clapperboard, Eye, Youtube, BarChart3, Zap, ArrowUpRight,
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { API_BASE_URL, apiFetch } from '@/lib/apiBase';

const display = Unbounded({
  subsets: ['latin', 'cyrillic'],
  weight: ['500', '700', '900'],
  display: 'swap',
});

type SystemStatus = 'checking' | 'online' | 'offline';

const STATIONS = [
  { href: '/trends', icon: TrendingUp, num: '01', title: 'home.stTrend', desc: 'home.stTrendDesc' },
  { href: '/generate', icon: PenLine, num: '02', title: 'home.stScript', desc: 'home.stScriptDesc' },
  { href: '/generate', icon: Clapperboard, num: '03', title: 'home.stRender', desc: 'home.stRenderDesc' },
  { href: '/review', icon: Eye, num: '04', title: 'home.stReview', desc: 'home.stReviewDesc' },
  { href: '/youtube', icon: Youtube, num: '05', title: 'home.stPublish', desc: 'home.stPublishDesc' },
] as const;

export default function Home() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SystemStatus>('checking');

  useEffect(() => {
    let cancelled = false;
    apiFetch(`${API_BASE_URL}/health`)
      .then((res) => { if (!cancelled) setStatus(res.ok ? 'online' : 'offline'); })
      .catch(() => { if (!cancelled) setStatus('offline'); });
    return () => { cancelled = true; };
  }, []);

  const statusLabel =
    status === 'online' ? t('home.statusOnline')
    : status === 'offline' ? t('home.statusOffline')
    : t('home.statusChecking');

  return (
    <div className="relative min-h-screen overflow-hidden flex flex-col">
      {/* Atmosphere: vignette + faint grid */}
      <div aria-hidden className="absolute inset-0 pointer-events-none">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_70%_-10%,rgba(20,184,166,0.13),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_10%_110%,rgba(245,158,11,0.07),transparent_55%)]" />
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(158,176,207,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(158,176,207,0.6) 1px, transparent 1px)',
            backgroundSize: '56px 56px',
          }}
        />
      </div>

      {/* ── Top bar: slate ── */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-10 py-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <Zap className="w-4 h-4 text-[var(--brand-1)]" />
          <span className={`${display.className} text-sm font-bold tracking-wide text-white`}>
            AI VIDEO FACTORY
          </span>
          <span className="hidden sm:inline-block font-mono text-[10px] uppercase tracking-[0.25em] text-[var(--muted)] border border-white/10 rounded px-2 py-0.5 ml-2">
            {t('home.internalStudio')}
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden md:flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-[var(--muted)]">
            <span
              className={`w-2 h-2 rounded-full ${
                status === 'online'
                  ? 'bg-[var(--brand-2)] landing-tally'
                  : status === 'offline'
                    ? 'bg-[var(--danger)]'
                    : 'bg-[var(--muted)]'
              }`}
            />
            {statusLabel}
          </div>
          <LanguageSwitcher />
        </div>
      </header>

      {/* ── Hero ── */}
      <main className="relative z-10 flex-1 flex flex-col justify-center px-6 sm:px-10 lg:px-16 py-12 max-w-6xl w-full mx-auto">
        <div className="landing-rise font-mono text-[11px] uppercase tracking-[0.35em] text-[var(--brand-1)] mb-6" style={{ animationDelay: '0.05s' }}>
          ● {t('home.tagline')}
        </div>

        <h1 className={`${display.className} landing-rise text-3xl sm:text-5xl lg:text-6xl font-black leading-[1.08] text-white mb-3`} style={{ animationDelay: '0.15s' }}>
          {t('home.heroLine1')}
        </h1>
        <h1 className={`${display.className} landing-rise text-3xl sm:text-5xl lg:text-6xl font-black leading-[1.08] mb-8 pb-1 text-transparent bg-clip-text bg-gradient-to-r from-[var(--brand-1)] to-emerald-300`} style={{ animationDelay: '0.25s' }}>
          {t('home.heroLine2')}
        </h1>

        <p className="landing-rise max-w-xl text-base sm:text-lg text-[var(--muted)] leading-relaxed mb-10" style={{ animationDelay: '0.35s' }}>
          {t('home.heroSub')}
        </p>

        <div className="landing-rise flex flex-wrap items-center gap-4 mb-16" style={{ animationDelay: '0.45s' }}>
          <Link
            href="/generate"
            className="group flex items-center gap-3 bg-[var(--brand-1)] text-[#04211c] px-7 py-3.5 rounded-[var(--radius-sm)] font-bold text-base hover:brightness-110 transition-all shadow-[0_16px_40px_rgba(20,184,166,0.25)]"
          >
            <Play className="w-4 h-4 fill-current" />
            {t('home.ctaStart')}
            <ArrowUpRight className="w-4 h-4 opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all" />
          </Link>
          <Link
            href="/trends"
            className="flex items-center gap-2 border border-white/15 text-white px-7 py-3.5 rounded-[var(--radius-sm)] font-medium text-base hover:border-[var(--brand-1)]/60 hover:bg-white/[0.03] transition-all"
          >
            <TrendingUp className="w-4 h-4 text-[var(--brand-1)]" />
            {t('home.ctaTrends')}
          </Link>
        </div>

        {/* ── Production line ── */}
        <div className="landing-rise" style={{ animationDelay: '0.55s' }}>
          <div className="flex items-center gap-3 mb-5">
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--muted)]">
              {t('home.pipeline')}
            </span>
            <span className="landing-belt flex-1 h-[2px]" aria-hidden />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {STATIONS.map((s, i) => (
              <Link
                key={s.num}
                href={s.href}
                className="landing-frame landing-rise group relative bg-[var(--surface-1)]/80 border border-white/[0.07] rounded-[var(--radius-sm)] p-4 hover:border-[var(--brand-1)]/50 hover:bg-[var(--surface-2)]/80 transition-all"
                style={{ animationDelay: `${0.65 + i * 0.08}s` }}
              >
                <div className="flex items-start justify-between mb-6">
                  <span className="font-mono text-[10px] text-[var(--muted)] group-hover:text-[var(--brand-1)] transition-colors">
                    {s.num}
                  </span>
                  <s.icon className="w-4 h-4 text-[var(--muted)] group-hover:text-[var(--brand-1)] transition-colors" />
                </div>
                <div className={`${display.className} text-sm font-bold text-white mb-1`}>
                  {t(s.title)}
                </div>
                <div className="text-[11px] text-[var(--muted)] leading-snug">{t(s.desc)}</div>
              </Link>
            ))}
          </div>
        </div>
      </main>

      {/* ── Bottom strip: edit-suite bar ── */}
      <footer className="relative z-10 flex items-center justify-between px-6 sm:px-10 py-4 border-t border-white/[0.06] font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">
        <span className="hidden sm:inline">REC ● {new Date().getFullYear()}</span>
        <span>TREND → SCRIPT → RENDER → REVIEW → PUBLISH</span>
        <Link href="/dashboard" className="flex items-center gap-1.5 hover:text-[var(--brand-1)] transition-colors">
          <BarChart3 className="w-3.5 h-3.5" />
          {t('home.analytics')}
        </Link>
      </footer>
    </div>
  );
}
