'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
    TrendingUp, Sparkles, ThumbsUp, Play, Loader2,
    RefreshCw, ArrowLeft, Tag, Star, Zap, Youtube, Globe, Search, XCircle, Eye,
    Music, ArrowUpRight, ArrowRight, ArrowDownRight, Target, ChevronDown, ChevronUp, Heart
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { safeArray, safeStringArray } from '@/lib/safeJson';
import { toErrorMessage } from '@/lib/errorUtils';
import { API_V1_BASE_URL } from '@/lib/apiBase';

interface TrendItem {
    id: number;
    title: string;
    description: string;
    source: string;
    category: string;
    score: number;
    keywords_json: string;
    url: string;
    fetched_at: string;
    velocity_score: number;
    trend_stage: string;
    competition_level: number | null;
    opportunity_score: number | null;
    view_count: number | null;
    published_at: string | null;
    thumbnail_url: string | null;
    content_type: string;
    subscriber_count: number | null;
    viral_coef: number | null;
    is_anomaly: boolean;
    matched_keyword: string | null;
    region: string | null;
}

interface TrendGenerateResult {
    success: boolean;
    project_id: number | null;
    idea_id: number | null;
    seo_title: string;
    seo_description: string;
    seo_tags: string[];
    seo_hashtags: string[];
    message: string;
}

interface StoryIdea {
    id: number;
    trend_id: number | null;
    idea_text: string;
    genre: string;
    virality_score: number;
    status: string;
    project_id: number | null;
    created_at: string;
    hook_type: string | null;
    suggested_title: string | null;
    suggested_tags_json: string | null;
    variants_json: string | null;
    narrative_structure: string | null;
    regenerable: string | null;
}

interface StoryIdeaVariant {
    hook_type?: string | null;
    angle?: string | null;
    suggested_title?: string | null;
}

function isStoryIdeaVariant(value: unknown): value is StoryIdeaVariant {
    if (!value || typeof value !== 'object') return false;
    const candidate = value as Record<string, unknown>;
    return (
        (candidate.hook_type === undefined || candidate.hook_type === null || typeof candidate.hook_type === 'string') &&
        (candidate.angle === undefined || candidate.angle === null || typeof candidate.angle === 'string') &&
        (candidate.suggested_title === undefined || candidate.suggested_title === null || typeof candidate.suggested_title === 'string')
    );
}

const SOURCE_CONFIG: Record<string, { label: string; icon: string; color: string; badgeClass: string }> = {
    youtube: {
        label: 'YouTube',
        icon: 'youtube',
        color: 'text-red-400',
        badgeClass: 'bg-red-500/20 text-red-400 border-red-500/30',
    },
    google_trends: {
        label: 'Google Trends',
        icon: 'globe',
        color: 'text-blue-400',
        badgeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    },
    instagram: {
        label: 'Instagram',
        icon: 'instagram',
        color: 'text-pink-400',
        badgeClass: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    },
    apify: {
        label: 'Social Media',
        icon: 'search',
        color: 'text-green-400',
        badgeClass: 'bg-green-500/20 text-green-400 border-green-500/30',
    },
    tiktok: {
        label: 'TikTok',
        icon: 'tiktok',
        color: 'text-pink-400',
        badgeClass: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    },
};

const CONTENT_TYPE_CONFIG: Record<string, { label: string; badgeClass: string }> = {
    ai_generated: { label: 'AI Generated', badgeClass: 'bg-purple-500/20 text-purple-400 border-purple-500/30' },
    animation: { label: 'Animation', badgeClass: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30' },
    story: { label: 'Story', badgeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
    skit: { label: 'Skit', badgeClass: 'bg-green-500/20 text-green-400 border-green-500/30' },
    music_video: { label: 'Music', badgeClass: 'bg-pink-500/20 text-pink-300 border-pink-500/30' },
    other: { label: 'Other', badgeClass: 'bg-gray-500/20 text-gray-400 border-gray-500/30' },
};

const HOOK_LABELS: Record<string, string> = {
    question: 'Question',
    shocking_stat: 'Shocking Stat',
    pov: 'POV',
    cliffhanger: 'Cliffhanger',
    contrast: 'Contrast',
    mistake_warning: 'Mistake Warning',
    pattern_interrupt: 'Pattern Interrupt',
    results_preview: 'Results Preview',
    countdown: 'Countdown',
    authority: 'Authority',
    emotional: 'Emotional',
    curiosity_gap: 'Curiosity Gap',
};

const SORT_OPTIONS = ['velocity', 'viral_coef', 'opportunity', 'score'] as const;
type SortBy = (typeof SORT_OPTIONS)[number];

function isSortBy(value: string): value is SortBy {
    return (SORT_OPTIONS as readonly string[]).includes(value);
}

export default function TrendsPage() {
    const { t } = useLanguage();
    const [trends, setTrends] = useState<TrendItem[]>([]);
    const [ideas, setIdeas] = useState<StoryIdea[]>([]);
    const [loading, setLoading] = useState(false);
    const [fetchingTrends, setFetchingTrends] = useState(false);
    const [analyzingTrends, setAnalyzingTrends] = useState(false);
    const [generatingIdea, setGeneratingIdea] = useState<number | null>(null);
    const [generatingTrend, setGeneratingTrend] = useState<number | null>(null);
    const [generatedResults, setGeneratedResults] = useState<Record<number, TrendGenerateResult>>({});
    const [region, setRegion] = useState('US');
    const [genreFilter, setGenreFilter] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [sourceFilter, setSourceFilter] = useState('');
    const [sortBy, setSortBy] = useState<SortBy>('viral_coef');
    const [anomalyOnly, setAnomalyOnly] = useState(false);
    const [favoritesOnly, setFavoritesOnly] = useState(false);
    const [favorites, setFavorites] = useState<Set<number>>(new Set());
    const [keywords, setKeywords] = useState<string[]>([]);
    const [keywordInput, setKeywordInput] = useState('');
    const [keywordFilter, setKeywordFilter] = useState('');
    const [platforms, setPlatforms] = useState<Set<string>>(new Set(['youtube', 'tiktok', 'instagram']));
    const [activeTab, setActiveTab] = useState<'trends' | 'ideas'>('trends');
    const [error, setError] = useState('');
    const [expandedVariants, setExpandedVariants] = useState<Set<number>>(new Set());

    const sourceCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        trends.forEach(t => { counts[t.source] = (counts[t.source] || 0) + 1; });
        return counts;
    }, [trends]);

    const anomalyCount = useMemo(() => trends.filter(t => t.is_anomaly).length, [trends]);

    const keywordCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        trends.forEach(t => {
            if (t.matched_keyword) counts[t.matched_keyword] = (counts[t.matched_keyword] || 0) + 1;
        });
        return counts;
    }, [trends]);

    const saveKeywords = (kws: string[]) => {
        setKeywords(kws);
        try { localStorage.setItem('trend_keywords', JSON.stringify(kws)); } catch { /* ignore */ }
    };

    const filteredAndSortedTrends = useMemo(() => {
        let filtered = sourceFilter ? trends.filter(t => t.source === sourceFilter) : trends;
        if (anomalyOnly) filtered = filtered.filter(t => t.is_anomaly);
        if (favoritesOnly) filtered = filtered.filter(t => favorites.has(t.id));
        if (keywordFilter) filtered = filtered.filter(t => t.matched_keyword === keywordFilter);
        const sorted = [...filtered];
        switch (sortBy) {
            case 'velocity':
                sorted.sort((a, b) => (b.velocity_score || 0) - (a.velocity_score || 0));
                break;
            case 'viral_coef':
                sorted.sort((a, b) => (b.viral_coef || 0) - (a.viral_coef || 0));
                break;
            case 'opportunity':
                sorted.sort((a, b) => (b.opportunity_score || 0) - (a.opportunity_score || 0));
                break;
            case 'score':
                sorted.sort((a, b) => b.score - a.score);
                break;
        }
        return sorted;
    }, [trends, sourceFilter, sortBy, anomalyOnly, favoritesOnly, favorites, keywordFilter]);

    const fetchTrendsList = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_V1_BASE_URL}/trends/?region=${region}&limit=100`);
            const data = await res.json();
            setTrends(data);
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setLoading(false);
        }
    }, [region]);

    const fetchIdeasList = useCallback(async () => {
        try {
            let url = `${API_V1_BASE_URL}/trends/ideas?limit=50`;
            if (statusFilter) url += `&status=${statusFilter}`;
            if (genreFilter) url += `&genre=${genreFilter}`;
            const res = await fetch(url);
            const data = await res.json();
            setIdeas(data);
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        }
    }, [statusFilter, genreFilter]);

    useEffect(() => {
        fetchTrendsList();
        fetchIdeasList();
    }, [fetchTrendsList, fetchIdeasList]);

    // Load favorites and keywords from localStorage
    useEffect(() => {
        try {
            const stored = localStorage.getItem('trend_favorites');
            if (stored) setFavorites(new Set(JSON.parse(stored)));
        } catch { /* ignore */ }
        try {
            const storedKws = localStorage.getItem('trend_keywords');
            if (storedKws) setKeywords(JSON.parse(storedKws));
        } catch { /* ignore */ }
    }, []);

    const toggleFavorite = (id: number) => {
        setFavorites(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            try { localStorage.setItem('trend_favorites', JSON.stringify([...next])); } catch { /* ignore */ }
            return next;
        });
    };

    const handleFetchTrends = async () => {
        setFetchingTrends(true);
        setError('');
        try {
            // Step 1: fetch trends from sources
            const res = await fetch(`${API_V1_BASE_URL}/trends/fetch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ region, max_per_source: 20, keywords, platforms: [...platforms] }),
            });
            const data = await res.json();
            if (data.success) {
                await fetchTrendsList();

                // Step 2: auto-analyze with AI to generate story ideas
                setAnalyzingTrends(true);
                try {
                    const analyzeRes = await fetch(`${API_V1_BASE_URL}/trends/analyze`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ max_ideas: 5, genre: genreFilter }),
                    });
                    const analyzeData = await analyzeRes.json();
                    if (analyzeData.success) {
                        await fetchIdeasList();
                    }
                } catch (e: unknown) {
                    // Analysis failure is non-critical — trends are already loaded
                    console.warn('[Trends] Auto-analyze failed:', toErrorMessage(e));
                } finally {
                    setAnalyzingTrends(false);
                }
            }
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setFetchingTrends(false);
        }
    };

    const handleApprove = async (ideaId: number) => {
        try {
            const res = await fetch(`${API_V1_BASE_URL}/trends/ideas/${ideaId}/approve`, { method: 'POST' });
            const data = await res.json();
            if (data.success) await fetchIdeasList();
        } catch (e: unknown) { setError(toErrorMessage(e)); }
    };

    const handleGenerate = async (ideaId: number) => {
        setGeneratingIdea(ideaId);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/trends/ideas/${ideaId}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: 'seedance', duration: 6, aspect_ratio: '9:16' }),
            });
            const data = await res.json();
            if (data.success) await fetchIdeasList();
        } catch (e: unknown) { setError(toErrorMessage(e)); }
        finally { setGeneratingIdea(null); }
    };

    const handleGenerateFromTrend = async (trendId: number) => {
        setGeneratingTrend(trendId);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/trends/${trendId}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ genre: 'drama', model: 'seedance', duration: 6, aspect_ratio: '9:16' }),
            });
            const data: TrendGenerateResult = await res.json();
            if (data.success) {
                setGeneratedResults(prev => ({ ...prev, [trendId]: data }));
            } else {
                setError(data.message || 'Generation failed');
            }
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setGeneratingTrend(null);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'pending': return 'bg-yellow-500/20 text-yellow-400';
            case 'approved': return 'bg-blue-500/20 text-blue-400';
            case 'generated': return 'bg-green-500/20 text-green-400';
            case 'published': return 'bg-purple-500/20 text-purple-400';
            default: return 'bg-gray-500/20 text-gray-400';
        }
    };

    const getGenreEmoji = (genre: string) => {
        const map: Record<string, string> = {
            drama: '\u{1F3AD}', comedy: '\u{1F602}', horror: '\u{1F47B}', thriller: '\u{1F52A}',
            romance: '\u2764\uFE0F', 'sci-fi': '\u{1F680}', mystery: '\u{1F50D}',
        };
        return map[genre] || '\u{1F3AC}';
    };

    const formatVelocity = (v: number) => {
        if (v >= 100000) return `${(v / 1000).toFixed(0)}K/hr`;
        if (v >= 10000) return `${(v / 1000).toFixed(1)}K/hr`;
        if (v >= 1000) return `${(v / 1000).toFixed(1)}K/hr`;
        if (v >= 1) return `${v.toFixed(0)}/hr`;
        return '';
    };

    const formatViewCount = (n: number) => {
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
        return String(n);
    };

    const formatScore = (trend: TrendItem) => {
        if (trend.source === 'youtube' || trend.source === 'tiktok') {
            // Show velocity as primary metric
            if (trend.velocity_score > 0) {
                return formatVelocity(trend.velocity_score);
            }
            if (trend.score >= 1000) return `${(trend.score / 1000).toFixed(1)}M views`;
            if (trend.score >= 1) return `${trend.score.toFixed(0)}K views`;
            return `${(trend.score * 1000).toFixed(0)} views`;
        }
        if (trend.source === 'google_trends') {
            if (trend.category === 'breakout') return 'BREAKOUT';
            return `Popularity: ${trend.score.toFixed(0)}`;
        }
        return `Score: ${trend.score.toFixed(0)}`;
    };

    const SourceIcon = ({ source, className }: { source: string; className?: string }) => {
        switch (source) {
            case 'youtube': return <Youtube className={className} />;
            case 'google_trends': return <Globe className={className} />;
            case 'apify': return <Search className={className} />;
            case 'tiktok': return <Music className={className} />;
            case 'instagram': return <Play className={className} />;
            default: return <TrendingUp className={className} />;
        }
    };

    const formatTimeAgo = (dateStr: string): string => {
        const d = new Date(dateStr);
        const hours = (Date.now() - d.getTime()) / 3_600_000;
        if (hours < 1) return 'только что';
        if (hours < 24) return 'сегодня';
        if (hours < 48) return 'вчера';
        const days = Math.floor(hours / 24);
        return `${days} дн. назад`;
    };

    const StageIcon = ({ stage }: { stage: string }) => {
        switch (stage) {
            case 'rising': return <ArrowUpRight className="w-3 h-3 text-green-400" />;
            case 'peaking': return <ArrowRight className="w-3 h-3 text-yellow-400" />;
            case 'declining': return <ArrowDownRight className="w-3 h-3 text-red-400" />;
            default: return null;
        }
    };

    const toggleVariants = (ideaId: number) => {
        setExpandedVariants(prev => {
            const next = new Set(prev);
            if (next.has(ideaId)) next.delete(ideaId);
            else next.add(ideaId);
            return next;
        });
    };

    const pendingIdeasCount = ideas.filter(i => i.status === 'pending').length;

    return (
        <div className="min-h-screen bg-[var(--background)] text-white">
            {/* Header */}
            <div className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Link href="/" className="text-gray-400 hover:text-white transition-colors">
                                <ArrowLeft className="w-5 h-5" />
                            </Link>
                            <h1 className="text-xl font-bold flex items-center gap-2">
                                <TrendingUp className="w-6 h-6 text-purple-400" />
                                {t('trends.title')}
                            </h1>
                        </div>
                        <div className="flex items-center gap-3">
                            <select value={region} onChange={(e) => setRegion(e.target.value)}
                                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
                                <option value="US">US</option>
                                <option value="GB">UK</option>
                                <option value="RU">Russia</option>
                                <option value="DE">Germany</option>
                                <option value="JP">Japan</option>
                                <option value="BR">Brazil</option>
                                <option value="IN">India</option>
                            </select>
                            <LanguageSwitcher />
                        </div>
                    </div>

                    {/* Workflow hint */}
                    <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
                        <span className="bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">1</span>
                        <span>{t('trends.step1')}</span>
                        <span className="text-gray-700">&rarr;</span>
                        <span className="bg-pink-500/20 text-pink-400 px-2 py-0.5 rounded">2</span>
                        <span>{t('trends.step2')}</span>
                        <span className="text-gray-700">&rarr;</span>
                        <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded">3</span>
                        <span>{t('trends.step3')}</span>
                        <span className="text-gray-700">&rarr;</span>
                        <span className="bg-green-500/20 text-green-400 px-2 py-0.5 rounded">4</span>
                        <span>{t('trends.step4')}</span>
                        <span className="text-gray-700">&rarr;</span>
                        <Link href="/review" className="flex items-center gap-1 text-orange-400 hover:text-orange-300">
                            <Eye className="w-3 h-3" /> {t('trends.reviewQueue')}
                        </Link>
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-6">
                {error && (
                    <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4 flex items-center justify-between">
                        <span>{error}</span>
                        <button onClick={() => setError('')} className="text-red-300 hover:text-white">
                            <XCircle className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* ====== Контент-радар (Trendsee-style config card) ====== */}
                <div className="bg-gray-800/40 border border-gray-700 rounded-xl p-4 mb-6">
                    <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                        {/* Left: status + keywords */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-sm font-semibold text-white">Ключевые слова</span>
                                <span className="text-xs text-gray-500">{keywords.length > 0 ? `${keywords.length} настроено` : 'не заданы — используются темы по умолчанию'}</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {keywords.map(kw => (
                                    <span key={kw} className="flex items-center gap-1 bg-gray-700/60 border border-gray-600 text-gray-200 text-sm px-3 py-1 rounded-lg">
                                        {kw}
                                        <button
                                            onClick={() => { saveKeywords(keywords.filter(k => k !== kw)); if (keywordFilter === kw) setKeywordFilter(''); }}
                                            className="ml-1 text-gray-500 hover:text-gray-200 leading-none text-base">×</button>
                                    </span>
                                ))}
                                <button
                                    onClick={() => { const inp = document.getElementById('kw-input') as HTMLInputElement; inp?.focus(); }}
                                    className="flex items-center gap-1 text-sm text-purple-400 hover:text-purple-300 px-2 py-1 border border-dashed border-purple-500/30 rounded-lg transition-colors">
                                    + Добавить слово
                                </button>
                            </div>
                            <input
                                id="kw-input"
                                value={keywordInput}
                                onChange={e => setKeywordInput(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === 'Enter' && keywordInput.trim()) {
                                        const kw = keywordInput.trim();
                                        if (!keywords.includes(kw)) saveKeywords([...keywords, kw]);
                                        setKeywordInput('');
                                    }
                                }}
                                placeholder="Введите ключевое слово и нажмите Enter"
                                className="mt-3 bg-gray-700/50 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 w-full sm:w-72"
                            />
                        </div>

                        {/* Center: platform selection */}
                        <div className="shrink-0">
                            <div className="text-xs text-gray-500 mb-2">Платформы поиска</div>
                            <div className="flex items-center gap-2">
                                {([
                                    { id: 'youtube', label: 'YouTube', icon: <Youtube className="w-4 h-4" />, color: 'text-red-500', active: 'bg-red-500/15 border-red-500/50 text-red-400' },
                                    { id: 'tiktok', label: 'TikTok', icon: <Music className="w-4 h-4" />, color: 'text-pink-400', active: 'bg-pink-500/15 border-pink-500/50 text-pink-300' },
                                    { id: 'instagram', label: 'Instagram', icon: <Play className="w-4 h-4" />, color: 'text-orange-400', active: 'bg-orange-500/15 border-orange-500/50 text-orange-300' },
                                ] as const).map(p => {
                                    const on = platforms.has(p.id);
                                    return (
                                        <button key={p.id}
                                            onClick={() => setPlatforms(prev => {
                                                const next = new Set(prev);
                                                if (next.has(p.id)) { if (next.size > 1) next.delete(p.id); }
                                                else next.add(p.id);
                                                return next;
                                            })}
                                            className={`flex items-center gap-1.5 border rounded-lg px-3 py-2 transition-colors ${on ? p.active : 'bg-gray-800/50 border-gray-700 text-gray-500 opacity-50'}`}>
                                            <span className={on ? p.color : ''}>{p.icon}</span>
                                            <span className="text-xs">{p.label}</span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Right: actions */}
                        <div className="shrink-0 flex flex-col gap-2 sm:items-end">
                            <button onClick={handleFetchTrends} disabled={fetchingTrends || analyzingTrends}
                                className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-5 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors whitespace-nowrap">
                                {(fetchingTrends || analyzingTrends) ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                                {analyzingTrends ? 'Анализ...' : fetchingTrends ? 'Загрузка...' : 'Загрузить тренды'}
                            </button>
                            {trends.length > 0 && (
                                <div className="text-xs text-gray-500 text-right">
                                    {trends.length} видео найдено
                                    {anomalyCount > 0 && <span className="text-red-400 ml-1">· {anomalyCount} аномалий</span>}
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Tabs */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex gap-1 bg-gray-800/50 rounded-lg p-1">
                        <button onClick={() => setActiveTab('trends')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === 'trends' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                            <TrendingUp className="w-4 h-4 inline mr-2" />
                            {t('trends.tabs.trends')} ({trends.length})
                        </button>
                        <button onClick={() => setActiveTab('ideas')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors relative ${activeTab === 'ideas' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'}`}>
                            <Sparkles className="w-4 h-4 inline mr-2" />
                            {t('trends.tabs.ideas')} ({ideas.length})
                            {pendingIdeasCount > 0 && activeTab !== 'ideas' && (
                                <span className="absolute -top-1 -right-1 bg-yellow-500 text-black text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">
                                    {pendingIdeasCount}
                                </span>
                            )}
                        </button>
                    </div>
                </div>

                {/* ========== TRENDS TAB ========== */}
                {activeTab === 'trends' && (
                    <div>
                        {/* Source filter chips + Sort */}
                        {trends.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2 mb-5">
                                <button onClick={() => setSourceFilter('')}
                                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${!sourceFilter ? 'bg-purple-600/30 border-purple-500/50 text-purple-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                    <TrendingUp className="w-3.5 h-3.5" /> {t('trends.allSources')}
                                    <span className="text-xs opacity-70">({trends.length})</span>
                                </button>
                                {Object.entries(sourceCounts).map(([source, count]) => {
                                    const config = SOURCE_CONFIG[source] || { label: source, color: 'text-gray-400', badgeClass: '' };
                                    return (
                                        <button key={source}
                                            onClick={() => setSourceFilter(sourceFilter === source ? '' : source)}
                                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${sourceFilter === source ? `${config.badgeClass}` : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                            <SourceIcon source={source} className={`w-3.5 h-3.5 ${config.color}`} />
                                            {config.label}
                                            <span className="text-xs opacity-70">({count})</span>
                                        </button>
                                    );
                                })}

                                <div className="ml-auto flex items-center gap-2">
                                    <select
                                        value={sortBy}
                                        onChange={(e) => setSortBy(isSortBy(e.target.value) ? e.target.value : 'velocity')}
                                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-gray-300">
                                        <option value="velocity">{t('trends.fastestGrowing')}</option>
                                        <option value="viral_coef">Viral Coef (X)</option>
                                        <option value="opportunity">{t('trends.bestOpportunity')}</option>
                                        <option value="score">{t('trends.mostViews')}</option>
                                    </select>
                                </div>
                            </div>
                        )}

                        {/* Keyword tabs (Trendsee-style) */}
                        {Object.keys(keywordCounts).length > 0 && (
                            <div className="flex flex-wrap items-center gap-2 mb-4">
                                <button onClick={() => setKeywordFilter('')}
                                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${!keywordFilter ? 'bg-purple-600/30 border-purple-500/50 text-purple-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                    Все видео <span className="opacity-60">({trends.length})</span>
                                </button>
                                {Object.entries(keywordCounts).map(([kw, count]) => (
                                    <button key={kw} onClick={() => setKeywordFilter(keywordFilter === kw ? '' : kw)}
                                        className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-colors ${keywordFilter === kw ? 'bg-blue-600/30 border-blue-500/50 text-blue-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-blue-500/40'}`}>
                                        <Tag className="w-3 h-3 opacity-60" />
                                        {kw} <span className="opacity-60">({count})</span>
                                    </button>
                                ))}
                            </div>
                        )}

                        {/* Anomaly + Favorites filters */}
                        {(anomalyCount > 0 || favorites.size > 0) && (
                            <div className="flex flex-wrap items-center gap-2 mb-5">
                                {anomalyCount > 0 && (
                                    <button onClick={() => setAnomalyOnly(!anomalyOnly)}
                                        className={`px-2.5 py-1 rounded-md text-xs font-bold border transition-colors ${anomalyOnly ? 'bg-red-600/30 border-red-500/50 text-red-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-red-500/50'}`}>
                                        🔥 Аномалии ({anomalyCount})
                                    </button>
                                )}
                                {favorites.size > 0 && (
                                    <button onClick={() => setFavoritesOnly(!favoritesOnly)}
                                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold border transition-colors ${favoritesOnly ? 'bg-pink-600/30 border-pink-500/50 text-pink-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-pink-500/50'}`}>
                                        <Heart className="w-3 h-3" fill={favoritesOnly ? 'currentColor' : 'none'} />
                                        Избранные ({favorites.size})
                                    </button>
                                )}
                            </div>
                        )}

                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                            </div>
                        ) : trends.length === 0 ? (
                            <div className="text-center py-20 text-gray-500">
                                <TrendingUp className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p className="text-lg">{t('trends.noTrends')}</p>
                                <p className="text-sm mt-2">Нет данных для региона <strong className="text-gray-300">{region}</strong> — нажмите «Загрузить тренды»</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
                                {filteredAndSortedTrends.map((trend) => {
                                    const keywords = safeStringArray(trend.keywords_json);
                                    const config = SOURCE_CONFIG[trend.source] || { label: trend.source, color: 'text-gray-400', badgeClass: 'bg-gray-500/20 text-gray-400 border-gray-500/30' };
                                    const isNew = trend.published_at
                                        ? (Date.now() - new Date(trend.published_at).getTime()) < 48 * 3_600_000
                                        : false;
                                    return (
                                        <div key={trend.id} className="bg-gray-900 rounded-2xl overflow-hidden flex flex-col group hover:ring-1 hover:ring-purple-500/40 transition-all">
                                            {/* ── Thumbnail ── */}
                                            <div className="relative aspect-[9/14] overflow-hidden bg-gray-800 flex-shrink-0">
                                                {trend.thumbnail_url ? (
                                                    <img
                                                        src={trend.source === 'instagram'
                                                            ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/v1/proxy/image?url=${encodeURIComponent(trend.thumbnail_url)}`
                                                            : trend.thumbnail_url}
                                                        alt={trend.title}
                                                        className="w-full h-full object-cover"
                                                        loading="lazy"
                                                        onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex items-center justify-center">
                                                        <SourceIcon source={trend.source} className={`w-10 h-10 ${config.color} opacity-20`} />
                                                    </div>
                                                )}

                                                {/* Platform badge — top left */}
                                                <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/70 backdrop-blur-sm px-2 py-1 rounded-lg">
                                                    <SourceIcon source={trend.source} className={`w-3 h-3 ${config.color}`} />
                                                    <span className="text-white text-[11px] font-semibold leading-none">{config.label}</span>
                                                </div>

                                                {/* Top-right actions */}
                                                <div className="absolute top-2 right-2 flex flex-col gap-1.5">
                                                    <button
                                                        onClick={e => { e.stopPropagation(); toggleFavorite(trend.id); }}
                                                        className="w-7 h-7 bg-black/70 backdrop-blur-sm rounded-full flex items-center justify-center transition-all hover:scale-110"
                                                    >
                                                        <Heart
                                                            className={`w-3.5 h-3.5 transition-colors ${favorites.has(trend.id) ? 'text-pink-500' : 'text-white/70'}`}
                                                            fill={favorites.has(trend.id) ? 'currentColor' : 'none'}
                                                        />
                                                    </button>
                                                    {trend.url && (
                                                        <a href={trend.url} target="_blank" rel="noopener noreferrer"
                                                           onClick={e => e.stopPropagation()}
                                                           className="w-7 h-7 bg-black/70 backdrop-blur-sm rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                                            <ArrowUpRight className="w-3.5 h-3.5 text-white" />
                                                        </a>
                                                    )}
                                                </div>

                                                {/* Bottom gradient + stats */}
                                                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black/70 to-transparent pt-10 pb-2.5 px-2.5">
                                                    {/* Badges row */}
                                                    <div className="flex items-center gap-1.5 mb-2">
                                                        {isNew && (
                                                            <span className="bg-green-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full leading-none">
                                                                Новый
                                                            </span>
                                                        )}
                                                        {trend.viral_coef != null && trend.viral_coef >= 2 && (
                                                            <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md leading-none ${trend.is_anomaly ? 'bg-red-600 text-white' : 'bg-blue-600 text-white'}`}>
                                                                X{Math.round(trend.viral_coef)}
                                                            </span>
                                                        )}
                                                        {trend.trend_stage && trend.trend_stage !== 'unknown' && (
                                                            <span className={`flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium leading-none ${
                                                                trend.trend_stage === 'rising' ? 'bg-green-500/40 text-green-300' :
                                                                trend.trend_stage === 'peaking' ? 'bg-yellow-500/40 text-yellow-300' :
                                                                'bg-red-500/40 text-red-300'
                                                            }`}>
                                                                <StageIcon stage={trend.trend_stage} />
                                                                {trend.trend_stage === 'rising' ? t('trends.rising') :
                                                                 trend.trend_stage === 'peaking' ? t('trends.peaking') : t('trends.declining')}
                                                            </span>
                                                        )}
                                                    </div>

                                                    {/* Stats row */}
                                                    <div className="flex items-center gap-3 text-white text-[11px]">
                                                        {trend.view_count != null && trend.view_count > 0 && (
                                                            <span className="flex items-center gap-1">
                                                                <Eye className="w-3 h-3 opacity-70" />
                                                                {formatViewCount(trend.view_count)}
                                                            </span>
                                                        )}
                                                        {trend.velocity_score > 0 && (
                                                            <span className="flex items-center gap-1 opacity-70">
                                                                <Zap className="w-3 h-3" />
                                                                {formatVelocity(trend.velocity_score)}
                                                            </span>
                                                        )}
                                                        {trend.subscriber_count != null && trend.subscriber_count > 0 && (
                                                            <span className="flex items-center gap-1 opacity-60">
                                                                <Star className="w-3 h-3" />
                                                                {formatViewCount(trend.subscriber_count)}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* ── Card body ── */}
                                            <div className="p-3 flex flex-col flex-1 gap-2">
                                                {/* Title */}
                                                <p className="text-white text-xs font-medium line-clamp-2 leading-relaxed">{trend.title}</p>

                                                {/* Date + tags */}
                                                <div className="flex items-center gap-2 flex-wrap">
                                                    {trend.published_at && (
                                                        <span className="text-gray-500 text-[10px]">{formatTimeAgo(trend.published_at)}</span>
                                                    )}
                                                    {keywords.slice(0, 2).map((kw: string, i: number) => (
                                                        <span key={i} className="text-[10px] text-gray-600 truncate max-w-[60px]">
                                                            #{kw.replace('sound:', '')}
                                                        </span>
                                                    ))}
                                                </div>

                                                {/* CTA */}
                                                {generatedResults[trend.id] ? (
                                                    <div className="mt-auto bg-green-500/10 border border-green-500/30 rounded-lg p-2">
                                                        <div className="flex items-center gap-1 mb-1">
                                                            <Sparkles className="w-3 h-3 text-green-400" />
                                                            <span className="text-[10px] text-green-400 font-medium">{t('trends.seoGenerated')}</span>
                                                        </div>
                                                        <p className="text-[10px] text-white line-clamp-1">{generatedResults[trend.id].seo_title}</p>
                                                        {generatedResults[trend.id].project_id && (
                                                            <Link href={`/generate?project=${generatedResults[trend.id].project_id}`}
                                                                className="text-[10px] text-green-400 hover:text-green-300 flex items-center gap-0.5 mt-1">
                                                                {t('trends.viewProject')} <ArrowUpRight className="w-2.5 h-2.5" />
                                                            </Link>
                                                        )}
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => handleGenerateFromTrend(trend.id)}
                                                        disabled={generatingTrend === trend.id}
                                                        className="mt-auto w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-3 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                                                    >
                                                        {generatingTrend === trend.id
                                                            ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('trends.analyzingTrend')}</>
                                                            : <><Sparkles className="w-3.5 h-3.5" /> {t('trends.generateSimilar')}</>
                                                        }
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}

                {/* ========== IDEAS TAB ========== */}
                {activeTab === 'ideas' && (
                    <div>
                        <div className="flex gap-3 mb-4">
                            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
                                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
                                <option value="">{t('trends.allStatuses')}</option>
                                <option value="pending">{t('trends.pending')}</option>
                                <option value="approved">{t('trends.approved')}</option>
                                <option value="generated">{t('trends.generated')}</option>
                                <option value="published">{t('trends.published')}</option>
                            </select>
                            <select value={genreFilter} onChange={(e) => setGenreFilter(e.target.value)}
                                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
                                <option value="">{t('trends.allGenres')}</option>
                                <option value="drama">{getGenreEmoji('drama')} Drama</option>
                                <option value="comedy">{getGenreEmoji('comedy')} Comedy</option>
                                <option value="horror">{getGenreEmoji('horror')} Horror</option>
                                <option value="thriller">{getGenreEmoji('thriller')} Thriller</option>
                                <option value="romance">{getGenreEmoji('romance')} Romance</option>
                                <option value="sci-fi">{getGenreEmoji('sci-fi')} Sci-Fi</option>
                                <option value="mystery">{getGenreEmoji('mystery')} Mystery</option>
                            </select>
                        </div>

                        {ideas.length === 0 ? (
                            <div className="text-center py-20 text-gray-500">
                                <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                <p className="text-lg">{t('trends.noIdeas')}</p>
                                <p className="text-sm mt-2">{t('trends.noIdeasHint')}</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {ideas.map((idea) => {
                                    const variants = safeArray<StoryIdeaVariant>(idea.variants_json, isStoryIdeaVariant);
                                    const tags = safeStringArray(idea.suggested_tags_json);
                                    const isExpanded = expandedVariants.has(idea.id);

                                    return (
                                        <div key={idea.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-5 hover:border-purple-500/50 transition-colors">
                                            {/* Header: genre + status + hook + virality */}
                                            <div className="flex items-center gap-2 mb-3 flex-wrap">
                                                <span className="text-lg">{getGenreEmoji(idea.genre)}</span>
                                                <span className="text-xs font-medium text-purple-400 uppercase">{idea.genre}</span>
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(idea.status)}`}>
                                                    {idea.status}
                                                </span>
                                                {idea.hook_type && (
                                                    <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">
                                                        Hook: {HOOK_LABELS[idea.hook_type] || idea.hook_type}
                                                    </span>
                                                )}
                                                {idea.regenerable && (
                                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                                        idea.regenerable.startsWith('yes')
                                                            ? 'bg-green-500/20 text-green-400'
                                                            : 'bg-red-500/20 text-red-400'
                                                    }`}>
                                                        {idea.regenerable.startsWith('yes') ? 'AI-ready' : idea.regenerable}
                                                    </span>
                                                )}
                                                <div className="ml-auto flex items-center gap-1">
                                                    <Zap className="w-3 h-3 text-yellow-400" />
                                                    <span className="text-xs text-yellow-400">{(idea.virality_score * 100).toFixed(0)}%</span>
                                                </div>
                                            </div>

                                            {/* Idea text */}
                                            <p className="text-sm text-gray-300 mb-2">{idea.idea_text}</p>

                                            {/* Narrative structure */}
                                            {idea.narrative_structure && (
                                                <div className="text-[10px] text-gray-500 mb-3 flex items-center gap-1">
                                                    <span>📐</span> {idea.narrative_structure}
                                                </div>
                                            )}

                                            {/* Suggested title */}
                                            {idea.suggested_title && (
                                                <div className="mb-3 bg-gray-700/30 rounded-lg p-2">
                                                    <span className="text-[10px] text-gray-500 uppercase font-medium">{t('trends.suggestedTitle')}</span>
                                                    <p className="text-xs text-gray-300 italic mt-0.5">&quot;{idea.suggested_title}&quot;</p>
                                                </div>
                                            )}

                                            {/* Suggested tags */}
                                            {tags.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mb-3">
                                                    {tags.map((tag: string, i: number) => (
                                                        <span key={i} className="text-[10px] bg-blue-500/15 text-blue-400 px-1.5 py-0.5 rounded">
                                                            #{tag}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}

                                            {/* Variants toggle */}
                                            {variants.length > 0 && (
                                                <div className="mb-3">
                                                    <button onClick={() => toggleVariants(idea.id)}
                                                        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors">
                                                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                                        {variants.length > 1 ? t('trends.alternativeAnglesPlural', { count: variants.length }) : t('trends.alternativeAngles', { count: variants.length })}
                                                    </button>
                                                    {isExpanded && (
                                                        <div className="mt-2 space-y-2">
                                                            {variants.map((v, idx: number) => (
                                                                <div key={idx} className="bg-gray-700/30 rounded-lg p-2 text-xs text-gray-400">
                                                                    <span className="text-purple-400 font-medium">
                                                                        {HOOK_LABELS[v.hook_type || ''] || v.hook_type || 'Hook'}:
                                                                    </span>{' '}
                                                                    {v.angle || ''}
                                                                    {v.suggested_title && (
                                                                        <div className="text-gray-500 mt-1 italic">&quot;{v.suggested_title}&quot;</div>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Action buttons */}
                                            <div className="flex gap-2">
                                                {idea.status === 'pending' && (
                                                    <>
                                                        <button onClick={() => handleApprove(idea.id)}
                                                            className="bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors">
                                                            <ThumbsUp className="w-3 h-3" /> {t('trends.approve')}
                                                        </button>
                                                        <button onClick={() => handleGenerate(idea.id)} disabled={generatingIdea === idea.id}
                                                            className="bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-700 hover:to-purple-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors">
                                                            {generatingIdea === idea.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                                            {t('trends.generate')}
                                                        </button>
                                                    </>
                                                )}
                                                {idea.status === 'approved' && (
                                                    <button onClick={() => handleGenerate(idea.id)} disabled={generatingIdea === idea.id}
                                                        className="bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-700 hover:to-purple-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors">
                                                        {generatingIdea === idea.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                                        {t('trends.generateVideo')}
                                                    </button>
                                                )}
                                                {idea.status === 'generated' && idea.project_id && (
                                                    <Link href={`/generate?project=${idea.project_id}`}
                                                        className="bg-green-600 hover:bg-green-700 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors">
                                                        {t('trends.viewProjectLink')}
                                                    </Link>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
