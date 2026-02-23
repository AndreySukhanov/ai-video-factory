'use client';

import Link from "next/link";
import { Play, PenLine, Video, Film, TrendingUp, Youtube, BarChart3, Eye } from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { Badge, Card, CardContent } from '@/components/ui';

export default function Home() {
  const { t } = useLanguage();

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center p-8 text-center overflow-hidden">
      <div className="absolute top-4 right-4">
        <LanguageSwitcher />
      </div>

      <Badge className="mb-5 bg-purple-500/15 text-purple-200 border-purple-400/35">{t('home.internalStudio')}</Badge>
      <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-violet-300 via-fuchsia-300 to-purple-400 text-transparent bg-clip-text">
        {t('home.title')}
      </h1>
      <p className="text-xl mb-8 max-w-2xl text-[var(--muted)]">
        {t('home.subtitle')}
      </p>

      <Link
        href="/generate"
        className="flex items-center gap-2 bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white px-8 py-4 rounded-[var(--radius-md)] font-semibold text-lg hover:brightness-110 transition-all shadow-[0_18px_40px_rgba(147,51,234,0.35)]"
      >
        <Play className="w-5 h-5" /> {t('home.startCreating')}
      </Link>

      <div className="mt-12 grid grid-cols-3 gap-8 text-center max-w-2xl">
        <div className="p-4 rounded-[var(--radius-md)] bg-white/5 border border-violet-400/20">
          <PenLine className="w-8 h-8 mx-auto mb-2 text-violet-300" />
          <div className="text-white font-medium">{t('home.writePrompts')}</div>
          <div className="text-[var(--muted)] text-sm">{t('home.writePromptsDesc')}</div>
        </div>
        <div className="p-4 rounded-[var(--radius-md)] bg-white/5 border border-fuchsia-400/20">
          <Video className="w-8 h-8 mx-auto mb-2 text-fuchsia-300" />
          <div className="text-white font-medium">{t('home.generateVideos')}</div>
          <div className="text-[var(--muted)] text-sm">{t('home.generateVideosDesc')}</div>
        </div>
        <div className="p-4 rounded-[var(--radius-md)] bg-white/5 border border-purple-400/20">
          <Film className="w-8 h-8 mx-auto mb-2 text-purple-300" />
          <div className="text-white font-medium">{t('home.buildSeries')}</div>
          <div className="text-[var(--muted)] text-sm">{t('home.buildSeriesDesc')}</div>
        </div>
      </div>

      {/* New features navigation */}
      <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl w-full">
        <Link href="/trends">
          <Card className="hover:border-violet-400/50 transition-colors">
            <CardContent className="p-4 flex flex-col items-center gap-2">
              <TrendingUp className="w-6 h-6 text-violet-300" />
              <span className="text-sm font-medium">{t('home.trends')}</span>
              <span className="text-[10px] text-[var(--muted)]">{t('home.trendsDesc')}</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/review">
          <Card className="hover:border-fuchsia-400/50 transition-colors">
            <CardContent className="p-4 flex flex-col items-center gap-2">
              <Eye className="w-6 h-6 text-fuchsia-300" />
              <span className="text-sm font-medium">{t('home.reviewQueue')}</span>
              <span className="text-[10px] text-[var(--muted)]">{t('home.reviewQueueDesc')}</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/youtube">
          <Card className="hover:border-purple-400/50 transition-colors">
            <CardContent className="p-4 flex flex-col items-center gap-2">
              <Youtube className="w-6 h-6 text-purple-300" />
              <span className="text-sm font-medium">{t('home.youtube')}</span>
              <span className="text-[10px] text-[var(--muted)]">{t('home.youtubeDesc')}</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/dashboard">
          <Card className="hover:border-violet-300/50 transition-colors">
            <CardContent className="p-4 flex flex-col items-center gap-2">
              <BarChart3 className="w-6 h-6 text-violet-200" />
              <span className="text-sm font-medium">{t('home.dashboard')}</span>
              <span className="text-[10px] text-[var(--muted)]">{t('home.dashboardDesc')}</span>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
