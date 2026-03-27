'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import {
    TrendingUp, Sparkles, ThumbsUp, Play, Loader2,
    RefreshCw, ArrowLeft, Tag, Star, Zap, Youtube, Globe, Search, XCircle, Eye,
    Music, ArrowUpRight, ArrowRight, ArrowDownRight, Target, ChevronDown, ChevronUp
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
    const [contentTypeFilter, setContentTypeFilter] = useState('');
    const [sortBy, setSortBy] = useState<SortBy>('velocity');
    const [anomalyOnly, setAnomalyOnly] = useState(false);
    const [activeTab, setActiveTab] = useState<'trends' | 'ideas'>('trends');
    const [error, setError] = useState('');
    const [expandedVariants, setExpandedVariants] = useState<Set<number>>(new Set());

    const sourceCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        trends.forEach(t => { counts[t.source] = (counts[t.source] || 0) + 1; });
        return counts;
    }, [trends]);

    const contentTypeCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        trends.forEach(t => {
            const ct = t.content_type || 'other';
            counts[ct] = (counts[ct] || 0) + 1;
        });
        return counts;
    }, [trends]);

    const actionableCount = useMemo(() => {
        return trends.filter(t => ['ai_generated', 'animation', 'story', 'skit', 'music_video'].includes(t.content_type || '')).length;
    }, [trends]);

    const anomalyCount = useMemo(() => trends.filter(t => t.is_anomaly).length, [trends]);

    const filteredAndSortedTrends = useMemo(() => {
        let filtered = sourceFilter ? trends.filter(t => t.source === sourceFilter) : trends;
        if (anomalyOnly) {
            filtered = filtered.filter(t => t.is_anomaly);
        }
        if (contentTypeFilter) {
            if (contentTypeFilter === '_actionable') {
                filtered = filtered.filter(t => ['ai_generated', 'animation', 'story', 'skit', 'music_video'].includes(t.content_type || ''));
            } else {
                filtered = filtered.filter(t => (t.content_type || 'other') === contentTypeFilter);
            }
        }
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
    }, [trends, sourceFilter, contentTypeFilter, sortBy]);

    const fetchTrendsList = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_V1_BASE_URL}/trends/?region=${region}&limit=50`);
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

    const handleFetchTrends = async () => {
        setFetchingTrends(true);
        setError('');
        try {
            // Step 1: fetch trends from sources
            const res = await fetch(`${API_V1_BASE_URL}/trends/fetch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ region, max_per_source: 20 }),
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
            default: return <TrendingUp className={className} />;
        }
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
                            <button onClick={handleFetchTrends} disabled={fetchingTrends || analyzingTrends}
                                className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors">
                                <Loader2 className={`w-4 h-4 ${(fetchingTrends || analyzingTrends) ? 'animate-spin' : 'hidden'}`} />
                                <RefreshCw className={`w-4 h-4 ${(fetchingTrends || analyzingTrends) ? 'hidden' : ''}`} />
                                {analyzingTrends ? t('trends.analyzeAI') : t('trends.fetchTrends')}
                            </button>
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

                        {/* Content type filter */}
                        {trends.length > 0 && (
                            <div className="flex flex-wrap items-center gap-2 mb-5">
                                <span className="text-xs text-gray-500 mr-1">{t('trends.contentType')}:</span>
                                <button onClick={() => setContentTypeFilter('')}
                                    className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${!contentTypeFilter ? 'bg-purple-600/30 border-purple-500/50 text-purple-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                    {t('trends.allTypes')} ({trends.length})
                                </button>
                                <button onClick={() => setContentTypeFilter(contentTypeFilter === '_actionable' ? '' : '_actionable')}
                                    className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${contentTypeFilter === '_actionable' ? 'bg-emerald-600/30 border-emerald-500/50 text-emerald-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                    {t('trends.aiReproducible')} ({actionableCount})
                                </button>
                                {anomalyCount > 0 && (
                                    <button onClick={() => setAnomalyOnly(!anomalyOnly)}
                                        className={`px-2.5 py-1 rounded-md text-xs font-bold border transition-colors ${anomalyOnly ? 'bg-red-600/30 border-red-500/50 text-red-300' : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-red-500/50'}`}>
                                        🔥 Аномалии ({anomalyCount})
                                    </button>
                                )}
                                {Object.entries(contentTypeCounts).map(([ct, count]) => {
                                    const cfg = CONTENT_TYPE_CONFIG[ct] || CONTENT_TYPE_CONFIG.other;
                                    return (
                                        <button key={ct}
                                            onClick={() => setContentTypeFilter(contentTypeFilter === ct ? '' : ct)}
                                            className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${contentTypeFilter === ct ? cfg.badgeClass : 'bg-gray-800/50 border-gray-700 text-gray-400 hover:border-gray-500'}`}>
                                            {cfg.label} ({count})
                                        </button>
                                    );
                                })}
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
                                <p className="text-sm mt-2">{t('trends.noTrendsHint')}</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {filteredAndSortedTrends.map((trend) => {
                                    const keywords = safeStringArray(trend.keywords_json);
                                    const config = SOURCE_CONFIG[trend.source] || { label: trend.source, color: 'text-gray-400', badgeClass: 'bg-gray-500/20 text-gray-400 border-gray-500/30' };
                                    return (
                                        <div key={trend.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 hover:border-purple-500/50 transition-colors flex flex-col">
                                            {/* Thumbnail */}
                                            {trend.thumbnail_url && (
                                                <div className="mb-2 -mx-4 -mt-4 rounded-t-xl overflow-hidden relative">
                                                    <img
                                                        src={trend.thumbnail_url}
                                                        alt={trend.title}
                                                        className="w-full h-32 object-cover"
                                                        loading="lazy"
                                                    />
                                                    {trend.viral_coef != null && trend.viral_coef >= 1 && (
                                                        <span className={`absolute top-1.5 left-1.5 text-[11px] font-bold px-1.5 py-0.5 rounded-md ${trend.is_anomaly ? 'bg-red-600 text-white' : 'bg-blue-600/90 text-white'}`}>
                                                            X{Math.round(trend.viral_coef)}
                                                        </span>
                                                    )}
                                                </div>
                                            )}
                                            {/* Viral badge (when no thumbnail) */}
                                            {!trend.thumbnail_url && trend.viral_coef != null && trend.viral_coef >= 1 && (
                                                <div className="flex justify-end mb-1">
                                                    <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${trend.is_anomaly ? 'bg-red-600 text-white' : 'bg-blue-600/90 text-white'}`}>
                                                        X{Math.round(trend.viral_coef)}
                                                    </span>
                                                </div>
                                            )}
                                            {/* Header: title + badges */}
                                            <div className="flex items-start justify-between mb-2">
                                                <h3 className="font-medium text-sm line-clamp-2 flex-1">{trend.title}</h3>
                                                <div className="flex flex-col items-end gap-1 ml-2">
                                                    <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border whitespace-nowrap ${config.badgeClass}`}>
                                                        <SourceIcon source={trend.source} className="w-3 h-3" />
                                                        {config.label}
                                                    </span>
                                                    {trend.content_type && trend.content_type !== 'other' && (
                                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border whitespace-nowrap ${(CONTENT_TYPE_CONFIG[trend.content_type] || CONTENT_TYPE_CONFIG.other).badgeClass}`}>
                                                            {(CONTENT_TYPE_CONFIG[trend.content_type] || CONTENT_TYPE_CONFIG.other).label}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {trend.description && (
                                                <p className="text-gray-400 text-xs line-clamp-2 mb-3">{trend.description}</p>
                                            )}

                                            {/* Metrics row */}
                                            <div className="flex flex-wrap items-center gap-2 mb-2">
                                                {/* Velocity / Score */}
                                                <div className="flex items-center gap-1">
                                                    <Zap className={`w-3 h-3 ${trend.velocity_score > 0 ? 'text-yellow-400' : 'text-gray-500'}`} />
                                                    <span className="text-xs text-gray-300 font-medium">{formatScore(trend)}</span>
                                                </div>

                                                {/* Subscriber count */}
                                                {trend.subscriber_count != null && trend.subscriber_count > 0 && (
                                                    <div className="flex items-center gap-1">
                                                        <Eye className="w-3 h-3 text-gray-500" />
                                                        <span className="text-[10px] text-gray-400">{formatViewCount(trend.subscriber_count)} subs</span>
                                                    </div>
                                                )}

                                                {/* Trend stage badge */}
                                                {trend.trend_stage && trend.trend_stage !== 'unknown' && (
                                                    <span className={`flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                                                        trend.trend_stage === 'rising' ? 'bg-green-500/20 text-green-400' :
                                                        trend.trend_stage === 'peaking' ? 'bg-yellow-500/20 text-yellow-400' :
                                                        'bg-red-500/20 text-red-400'
                                                    }`}>
                                                        <StageIcon stage={trend.trend_stage} />
                                                        {trend.trend_stage === 'rising' ? t('trends.rising') :
                                                         trend.trend_stage === 'peaking' ? t('trends.peaking') : t('trends.declining')}
                                                    </span>
                                                )}

                                                {/* Breakout badge for Google Trends */}
                                                {trend.category === 'breakout' && (
                                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold bg-orange-500/30 text-orange-300 animate-pulse">
                                                        BREAKOUT
                                                    </span>
                                                )}
                                            </div>

                                            {/* Competition & Opportunity */}
                                            {(trend.competition_level != null || trend.opportunity_score != null) && (
                                                <div className="flex items-center gap-3 mb-2">
                                                    {trend.competition_level != null && (
                                                        <span className={`text-[10px] ${
                                                            trend.competition_level > 0.6 ? 'text-red-400' :
                                                            trend.competition_level > 0.3 ? 'text-yellow-400' : 'text-green-400'
                                                        }`}>
                                                            {t('trends.competition')}{trend.competition_level > 0.6 ? t('trends.competitionHigh') :
                                                                          trend.competition_level > 0.3 ? t('trends.competitionMedium') : t('trends.competitionLow')}
                                                        </span>
                                                    )}
                                                    {trend.opportunity_score != null && trend.opportunity_score > 0 && (
                                                        <div className="flex items-center gap-1">
                                                            <Target className={`w-3 h-3 ${
                                                                trend.opportunity_score > 0.6 ? 'text-green-400' :
                                                                trend.opportunity_score > 0.3 ? 'text-yellow-400' : 'text-gray-500'
                                                            }`} />
                                                            <span className="text-[10px] text-gray-400">
                                                                {t('trends.opportunity')}{(trend.opportunity_score * 100).toFixed(0)}%
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            )}

                                            {/* Keywords */}
                                            {keywords.length > 0 && (
                                                <div className="flex flex-wrap gap-1 mb-2">
                                                    {keywords.slice(0, 5).map((kw: string, i: number) => (
                                                        <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded ${
                                                            kw.startsWith('sound:')
                                                                ? 'bg-pink-500/20 text-pink-400'
                                                                : 'bg-gray-700/50 text-gray-400'
                                                        }`}>
                                                            {kw.startsWith('sound:') ? `${kw.replace('sound:', '')}` : kw}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}

                                            {trend.url && (
                                                <a href={trend.url} target="_blank" rel="noopener noreferrer"
                                                   className="text-xs text-purple-400 hover:text-purple-300 mt-1 block">
                                                    {t('trends.viewSource')}
                                                </a>
                                            )}

                                            {/* Generate Similar button */}
                                            {!generatedResults[trend.id] && (
                                                <button
                                                    onClick={() => handleGenerateFromTrend(trend.id)}
                                                    disabled={generatingTrend === trend.id}
                                                    className="mt-auto pt-3 w-full bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-700 hover:to-purple-700 disabled:opacity-50 px-3 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-colors"
                                                >
                                                    {generatingTrend === trend.id
                                                        ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('trends.analyzingTrend')}</>
                                                        : <><Zap className="w-3.5 h-3.5" /> {t('trends.generateSimilar')}</>
                                                    }
                                                </button>
                                            )}

                                            {/* Generated result */}
                                            {generatedResults[trend.id] && (
                                                <div className="mt-auto pt-3 bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                                                    <div className="flex items-center gap-1.5 mb-2">
                                                        <Sparkles className="w-3.5 h-3.5 text-green-400" />
                                                        <span className="text-[10px] text-green-400 font-medium uppercase">{t('trends.seoGenerated')}</span>
                                                    </div>
                                                    <p className="text-xs text-white font-medium mb-2 line-clamp-2">
                                                        {generatedResults[trend.id].seo_title}
                                                    </p>
                                                    {generatedResults[trend.id].seo_tags.length > 0 && (
                                                        <div className="flex flex-wrap gap-1 mb-2">
                                                            {generatedResults[trend.id].seo_tags.slice(0, 8).map((tag, i) => (
                                                                <span key={i} className="text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded">
                                                                    #{tag}
                                                                </span>
                                                            ))}
                                                            {generatedResults[trend.id].seo_tags.length > 8 && (
                                                                <span className="text-[10px] text-gray-500">
                                                                    {t('trends.more', { count: generatedResults[trend.id].seo_tags.length - 8 })}
                                                                </span>
                                                            )}
                                                        </div>
                                                    )}
                                                    {generatedResults[trend.id].project_id && (
                                                        <Link href={`/generate?project=${generatedResults[trend.id].project_id}`}
                                                            className="text-xs text-green-400 hover:text-green-300 font-medium flex items-center gap-1">
                                                            {t('trends.viewProject')} <ArrowUpRight className="w-3 h-3" />
                                                        </Link>
                                                    )}
                                                </div>
                                            )}
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
