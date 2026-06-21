'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, ExternalLink, Sparkles, Loader2, RefreshCw,
  AlertCircle, Film, Eye, TrendingUp, BookOpen, Users, Image as ImageIcon,
} from 'lucide-react';
import { API_V1_BASE_URL } from '@/lib/apiBase';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';

interface Trend {
  id: number;
  title: string;
  source: string;
  url: string;
  region: string;
  niche: string | null;
  view_count: number | null;
  velocity_score: number | null;
  viral_coef: number | null;
  thumbnail_url: string | null;
  published_at: string | null;
  description: string | null;
}

interface StoryBeat { start: number; end: number; what_happens: string; emotion: string }
interface Character { role: string; gender: string; age_range: string; appearance: string; voice_tone: string }
interface VisualStyle { lighting?: string; location?: string; framing?: string; color_palette?: string }
interface CtaStructure { app_name?: string | null; cta_phrase?: string; position?: string }

interface Pattern {
  id: number;
  trend_id: number;
  transcript_source: string | null;
  hook: string | null;
  story_beats_json: string | null;
  characters_json: string | null;
  title_formula: string | null;
  cta_structure_json: string | null;
  visual_style_json: string | null;
  viral_mechanic: string | null;
  adaptation_brief: string | null;
  anchor_prompt: string | null;
  character_card: string | null;
  extracted_at: string | null;
  llm_model: string | null;
}

interface CloneBrief {
  success: boolean;
  idea?: string;
  genre?: string;
  episodes_count?: number;
  duration?: number;
  aspect_ratio?: string;
  anchor_prompt?: string;
  character_card?: string;
  suggested_title?: string;
  title_formula?: string;
  viral_mechanic?: string;
  error?: string;
}

function safeParse<T>(json: string | null | undefined, fallback: T): T {
  if (!json) return fallback;
  try { return JSON.parse(json) as T; } catch { return fallback; }
}

function formatViews(n: number | null | undefined): string {
  if (!n) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

export default function ClonePage() {
  const { t } = useLanguage();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const trendId = Number(params?.id);

  const [trend, setTrend] = useState<Trend | null>(null);
  const [pattern, setPattern] = useState<Pattern | null>(null);
  const [brief, setBrief] = useState<CloneBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    if (!trendId) return;
    setLoading(true);
    setError(null);
    try {
      // Trend basic info — direct lookup by id
      const tRes = await fetch(`${API_V1_BASE_URL}/trends/by-id/${trendId}`);
      if (tRes.ok) {
        const t: Trend = await tRes.json();
        setTrend(t);
      } else if (tRes.status === 404) {
        setError('Тренд не найден. Возможно, был стёрт следующим фетчем.');
      }

      // Existing pattern (if any)
      const pr = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/pattern`);
      const pd = await pr.json();
      if (pd.success && pd.pattern) setPattern(pd.pattern);

      // Brief — auto-extracts pattern if missing
      const br = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/clone-brief`, { method: 'POST' });
      const bd = await br.json();
      if (bd.success) {
        setBrief(bd);
        // If pattern was just extracted (wasn't there before), re-fetch
        if (!pd.success) {
          const pr2 = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/pattern`);
          const pd2 = await pr2.json();
          if (pd2.success && pd2.pattern) setPattern(pd2.pattern);
        }
      } else {
        setError(bd.error || 'Не удалось получить бриф');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [trendId]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleReExtract = async () => {
    setExtracting(true);
    setError(null);
    try {
      const r = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/extract-pattern`, { method: 'POST' });
      const d = await r.json();
      if (d.success && d.pattern) {
        setPattern(d.pattern);
        // Also refresh brief
        const br = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/clone-brief`, { method: 'POST' });
        const bd = await br.json();
        if (bd.success) setBrief(bd);
      } else {
        setError(d.error || 'Re-extraction failed');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setExtracting(false);
    }
  };

  const handleOpenInWizard = () => {
    if (!brief) return;
    try { sessionStorage.setItem('clone_brief', JSON.stringify(brief)); } catch { /* ignore */ }
    router.push('/generate?source=clone');
  };

  const beats = safeParse<StoryBeat[]>(pattern?.story_beats_json, []);
  const characters = safeParse<Character[]>(pattern?.characters_json, []);
  const visualStyle = safeParse<VisualStyle>(pattern?.visual_style_json, {});
  const cta = safeParse<CtaStructure | null>(pattern?.cta_structure_json, null);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/70 backdrop-blur sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/trends" className="text-gray-400 hover:text-white flex items-center gap-1.5 text-sm">
              <ArrowLeft className="w-4 h-4" /> {t('clone.backToTrends')}
            </Link>
            <h1 className="text-lg font-bold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              {t('clone.title')}
            </h1>
          </div>
          <LanguageSwitcher />
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6 space-y-6">
        {loading && (
          <div className="flex items-center gap-2 text-gray-400">
            <Loader2 className="w-4 h-4 animate-spin" /> {t('clone.loading')}
          </div>
        )}

        {error && (
          <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-3 text-sm text-red-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> {error}
          </div>
        )}

        {/* Original */}
        {trend && (
          <section className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800 flex items-center gap-2">
              <Film className="w-4 h-4 text-blue-400" />
              <h2 className="font-semibold">{t('clone.originalSection')}</h2>
            </div>
            <div className="flex gap-4 p-4">
              {trend.thumbnail_url && (
                <div className="shrink-0">
                  <Link href={trend.url} target="_blank" rel="noreferrer" className="block">
                    <img src={trend.thumbnail_url} alt="thumb" className="w-40 h-auto rounded-lg object-cover" />
                  </Link>
                </div>
              )}
              <div className="flex-1 space-y-2 min-w-0">
                <h3 className="font-medium leading-tight">{trend.title}</h3>
                <div className="flex flex-wrap gap-3 text-xs text-gray-400">
                  <span className="bg-gray-800 px-2 py-0.5 rounded uppercase">{trend.source}</span>
                  <span>{trend.region}</span>
                  {trend.niche && <span className="bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded">{trend.niche}</span>}
                  <span className="flex items-center gap-1"><Eye className="w-3 h-3" /> {formatViews(trend.view_count)}</span>
                  {trend.viral_coef && <span className="flex items-center gap-1"><TrendingUp className="w-3 h-3" /> {trend.viral_coef.toFixed(1)}×</span>}
                </div>
                <Link href={trend.url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300">
                  {t('clone.watchOriginal')} <ExternalLink className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </section>
        )}

        {/* Pattern */}
        {pattern && (
          <section className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-pink-400" />
                <h2 className="font-semibold">{t('clone.patternSection')}</h2>
                {pattern.viral_mechanic && (
                  <span className="text-[10px] bg-pink-500/20 text-pink-300 px-2 py-0.5 rounded uppercase">{pattern.viral_mechanic}</span>
                )}
              </div>
              <button onClick={handleReExtract} disabled={extracting}
                className="text-xs flex items-center gap-1 px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-50">
                {extracting ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                {t('clone.reExtract')}
              </button>
            </div>
            <div className="p-4 space-y-4 text-sm">
              {pattern.hook && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.hook')}</div>
                  <div className="bg-gray-800/50 rounded px-3 py-2 italic">{pattern.hook}</div>
                </div>
              )}

              {pattern.title_formula && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.titleFormula')}</div>
                  <div className="bg-gray-800/50 rounded px-3 py-2 font-mono text-xs">{pattern.title_formula}</div>
                </div>
              )}

              {beats.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.storyBeats')}</div>
                  <ol className="space-y-1.5">
                    {beats.map((b, i) => (
                      <li key={i} className="flex gap-3 items-start">
                        <span className="shrink-0 text-xs font-mono bg-gray-800 px-1.5 py-0.5 rounded text-gray-400 w-20 text-center">
                          {b.start.toFixed(0)}–{b.end.toFixed(0)}s
                        </span>
                        <span className="flex-1">{b.what_happens}</span>
                        {b.emotion && <span className="shrink-0 text-[10px] bg-pink-500/10 text-pink-300 px-1.5 py-0.5 rounded uppercase">{b.emotion}</span>}
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {characters.length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1"><Users className="w-3 h-3" /> {t('clone.characters')}</div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {characters.map((c, i) => (
                      <div key={i} className="bg-gray-800/50 rounded px-3 py-2 text-xs">
                        <div className="font-medium">{c.role} {c.gender && <span className="text-gray-400">({c.gender}, {c.age_range})</span>}</div>
                        {c.appearance && <div className="text-gray-400 mt-0.5">{c.appearance}</div>}
                        {c.voice_tone && <div className="text-gray-500 mt-0.5 italic">voice: {c.voice_tone}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(visualStyle).length > 0 && (
                <div>
                  <div className="text-xs text-gray-500 mb-1 flex items-center gap-1"><ImageIcon className="w-3 h-3" /> {t('clone.visualStyle')}</div>
                  <div className="grid sm:grid-cols-2 gap-1.5 text-xs">
                    {visualStyle.lighting && <div className="bg-gray-800/50 rounded px-2 py-1"><span className="text-gray-500">lighting:</span> {visualStyle.lighting}</div>}
                    {visualStyle.location && <div className="bg-gray-800/50 rounded px-2 py-1"><span className="text-gray-500">location:</span> {visualStyle.location}</div>}
                    {visualStyle.framing && <div className="bg-gray-800/50 rounded px-2 py-1"><span className="text-gray-500">framing:</span> {visualStyle.framing}</div>}
                    {visualStyle.color_palette && <div className="bg-gray-800/50 rounded px-2 py-1"><span className="text-gray-500">colors:</span> {visualStyle.color_palette}</div>}
                  </div>
                </div>
              )}

              {cta && (cta.app_name || cta.cta_phrase) && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.cta')}</div>
                  <div className="bg-purple-500/10 border border-purple-500/30 rounded px-3 py-2 text-xs">
                    {cta.app_name && <div><span className="text-gray-400">app:</span> <span className="font-medium">{cta.app_name}</span></div>}
                    {cta.cta_phrase && <div><span className="text-gray-400">phrase:</span> {cta.cta_phrase}</div>}
                    {cta.position && <div className="text-gray-500">position: {cta.position}</div>}
                  </div>
                </div>
              )}

              <div className="text-[10px] text-gray-600 pt-2 border-t border-gray-800 flex gap-3">
                {pattern.transcript_source && <span>transcript: {pattern.transcript_source}</span>}
                {pattern.llm_model && <span>llm: {pattern.llm_model}</span>}
                {pattern.extracted_at && <span>extracted: {new Date(pattern.extracted_at).toLocaleString()}</span>}
              </div>
            </div>
          </section>
        )}

        {/* Brief */}
        {brief && brief.success && (
          <section className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-gray-800 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-green-400" />
              <h2 className="font-semibold">{t('clone.briefSection')}</h2>
            </div>
            <div className="p-4 space-y-3 text-sm">
              {brief.idea && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.brief.idea')}</div>
                  <div className="bg-gray-800/50 rounded px-3 py-2">{brief.idea}</div>
                </div>
              )}
              {brief.character_card && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.brief.characterCard')}</div>
                  <div className="bg-gray-800/50 rounded px-3 py-2 text-xs leading-relaxed">{brief.character_card}</div>
                </div>
              )}
              {brief.anchor_prompt && (
                <div>
                  <div className="text-xs text-gray-500 mb-1">{t('clone.brief.anchorPrompt')}</div>
                  <div className="bg-gray-800/50 rounded px-3 py-2 text-xs leading-relaxed">{brief.anchor_prompt}</div>
                </div>
              )}
              <div className="flex gap-3 text-xs text-gray-400">
                <span>{t('clone.brief.episodes')}: <span className="text-white">{brief.episodes_count}</span></span>
                <span>{t('clone.brief.duration')}: <span className="text-white">{brief.duration}s</span></span>
                <span>{t('clone.brief.aspect')}: <span className="text-white">{brief.aspect_ratio}</span></span>
                <span>{t('clone.brief.genre')}: <span className="text-white">{brief.genre}</span></span>
              </div>

              <button
                onClick={handleOpenInWizard}
                className="w-full bg-purple-600 hover:bg-purple-700 px-4 py-2.5 rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                {t('clone.openInWizard')}
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
