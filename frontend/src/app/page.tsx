'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
  Play, TrendingUp, BarChart3, Zap, ArrowUpRight,
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { API_BASE_URL, apiFetch } from '@/lib/apiBase';
import { display } from '@/lib/fonts';
import IdeaPortal from '@/components/IdeaPortal';

type SystemStatus = 'checking' | 'online' | 'offline';

const STATIONS = [
  { href: '/trends', icon: '/icons/trend.jpg', num: '01', title: 'home.stTrend', desc: 'home.stTrendDesc' },
  { href: '/generate', icon: '/icons/script.jpg', num: '02', title: 'home.stScript', desc: 'home.stScriptDesc' },
  { href: '/generate', icon: '/icons/render.jpg', num: '03', title: 'home.stRender', desc: 'home.stRenderDesc' },
  { href: '/review', icon: '/icons/review.jpg', num: '04', title: 'home.stReview', desc: 'home.stReviewDesc' },
  { href: '/youtube', icon: '/icons/publish.jpg', num: '05', title: 'home.stPublish', desc: 'home.stPublishDesc' },
] as const;

export default function Home() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SystemStatus>('checking');
  const [portalOpen, setPortalOpen] = useState(false);

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
        <div className="lg:flex lg:items-center lg:gap-14 mb-16">
          <div className="flex-1 min-w-0">
            <div className="landing-rise font-mono text-[11px] uppercase tracking-[0.35em] text-[var(--brand-1)] mb-6" style={{ animationDelay: '0.05s' }}>
              ● {t('home.tagline')}
            </div>

            <h1 className={`${display.className} landing-rise text-3xl sm:text-5xl lg:text-[52px] xl:text-6xl font-black leading-[1.08] text-white mb-3`} style={{ animationDelay: '0.15s' }}>
              {t('home.heroLine1')}
            </h1>
            <h1 className={`${display.className} landing-rise text-3xl sm:text-5xl lg:text-[52px] xl:text-6xl font-black leading-[1.08] mb-8 pb-1 text-transparent bg-clip-text bg-gradient-to-r from-[var(--brand-1)] to-emerald-300`} style={{ animationDelay: '0.25s' }}>
              {t('home.heroLine2')}
            </h1>

            <p className="landing-rise max-w-xl text-base sm:text-lg text-[var(--muted)] leading-relaxed mb-10" style={{ animationDelay: '0.35s' }}>
              {t('home.heroSub')}
            </p>

            <div className="landing-rise flex flex-wrap items-center gap-4" style={{ animationDelay: '0.45s' }}>
              <button
                type="button"
                onClick={() => setPortalOpen(true)}
                aria-label={t('home.ctaPortal')}
                className="portal-cta group relative inline-flex rounded-full p-[2px]"
              >
                {/* pulsing halo */}
                <span aria-hidden className="portal-halo absolute -inset-4 rounded-full blur-xl pointer-events-none" />
                {/* spinning portal rim */}
                <span aria-hidden className="portal-rim absolute inset-0 rounded-full" />
                {/* dark core with the label */}
                <span className="relative z-10 flex items-center gap-3 rounded-full bg-[#04140f] text-white px-7 py-3.5 font-bold text-base group-hover:bg-[#052019] transition-colors">
                  <span aria-hidden className="relative w-4 h-4 shrink-0">
                    <span className="portal-swirl absolute inset-0 rounded-full" />
                    <span className="absolute inset-[3px] rounded-full bg-[#04140f]" />
                  </span>
                  {t('home.ctaPortal')}
                  <ArrowUpRight className="w-4 h-4 text-[var(--brand-1)] opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all" />
                </span>
              </button>
              <Link
                href="/generate"
                className="flex items-center gap-2 border border-white/15 text-white px-7 py-3.5 rounded-[var(--radius-sm)] font-medium text-base hover:border-[var(--brand-1)]/60 hover:bg-white/[0.03] transition-all"
              >
                <Play className="w-4 h-4 fill-current text-[var(--brand-1)]" />
                {t('home.ctaStart')}
              </Link>
              <Link
                href="/trends"
                className="flex items-center gap-2 border border-white/15 text-white px-7 py-3.5 rounded-[var(--radius-sm)] font-medium text-base hover:border-[var(--brand-1)]/60 hover:bg-white/[0.03] transition-all"
              >
                <TrendingUp className="w-4 h-4 text-[var(--brand-1)]" />
                {t('home.ctaTrends')}
              </Link>
            </div>
          </div>

          {/* Hero visual: the factory's own render, framed as a live monitor */}
          <div className="landing-rise hidden lg:block shrink-0 w-[280px] xl:w-[320px] lg:rotate-[1.2deg] hover:rotate-0 transition-transform duration-500" style={{ animationDelay: '0.4s' }}>
            <div className="relative rounded-[var(--radius-md)] overflow-hidden border border-white/10 shadow-[0_35px_90px_rgba(5,11,24,0.65)]">
              <Image
                src="/landing-hero.jpg"
                alt={t('home.heroImageAlt')}
                width={768}
                height={1376}
                priority
                unoptimized
                className="w-full h-auto"
              />
              <div className="absolute top-0 inset-x-0 flex items-center justify-between px-3 py-2.5 bg-gradient-to-b from-black/70 to-transparent font-mono text-[9px] tracking-[0.25em] text-white/85">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--brand-2)] landing-tally" />
                  REC
                </span>
                <span>9:16 · 24FPS</span>
              </div>
              <div className="absolute bottom-0 inset-x-0 flex items-center justify-between px-3 py-2.5 bg-gradient-to-t from-black/75 to-transparent font-mono text-[9px] tracking-[0.25em] text-white/70">
                <span>ST.03 — RENDER</span>
                <span className="text-[var(--brand-1)]">▶</span>
              </div>
            </div>
          </div>
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
                <div className="flex items-start justify-between mb-4">
                  <Image
                    src={s.icon}
                    alt=""
                    width={48}
                    height={48}
                    unoptimized
                    className="w-12 h-12 rounded-[var(--radius-sm)] ring-1 ring-white/10 group-hover:ring-[var(--brand-1)]/40 transition-all"
                  />
                  <span className="font-mono text-[10px] text-[var(--muted)] group-hover:text-[var(--brand-1)] transition-colors">
                    {s.num}
                  </span>
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

      <IdeaPortal open={portalOpen} onClose={() => setPortalOpen(false)} />
    </div>
  );
}
