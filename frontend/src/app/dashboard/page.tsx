'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
    BarChart3, Eye, ThumbsUp, MessageCircle, Clock, Users,
    Activity, Server, Database, Key, Youtube, TrendingUp,
    ArrowLeft, RefreshCw, Loader2, CheckCircle, XCircle, AlertTriangle, Zap, Bell
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { display } from '@/lib/fonts';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { toErrorMessage } from '@/lib/errorUtils';
import { API_V1_BASE_URL, apiFetch } from '@/lib/apiBase';

interface AnalyticsSummary {
    total_videos: number;
    total_views: number;
    total_likes: number;
    total_comments: number;
    total_watch_time_minutes: number;
    avg_views_per_video: number;
    avg_ctr: number;
    total_subscriber_gain: number;
}

interface HealthStatus {
    overall: boolean;
    redis: { healthy: boolean; used_memory_human?: string; error?: string };
    worker: { healthy: boolean; worker_count?: number; error?: string };
    api_keys: { healthy: boolean; configured: Record<string, boolean>; configured_count: number };
    youtube_quota: { healthy: boolean; remaining?: number; used?: number; daily_limit?: number; max_uploads_remaining?: number };
    timestamp: string;
}

interface VideoAnalyticsItem {
    id: number;
    youtube_video_id: string;
    views: number;
    likes: number;
    comments: number;
    watch_time_minutes: number;
    average_view_duration_seconds: number;
    click_through_rate: number;
    subscriber_gain: number;
    fetched_at: string;
}

export default function DashboardPage() {
    const { t } = useLanguage();
    const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
    const [health, setHealth] = useState<HealthStatus | null>(null);
    const [videos, setVideos] = useState<VideoAnalyticsItem[]>([]);
    const [wsBalance, setWsBalance] = useState<{ configured: boolean; balance: number | null } | null>(null);
    const [loading, setLoading] = useState(true);
    const [alerting, setAlerting] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [summaryRes, healthRes, videosRes, balanceRes] = await Promise.all([
                apiFetch(`${API_V1_BASE_URL}/analytics/summary`),
                apiFetch(`${API_V1_BASE_URL}/analytics/health`),
                apiFetch(`${API_V1_BASE_URL}/analytics/videos?limit=20`),
                apiFetch(`${API_V1_BASE_URL}/analytics/wavespeed-balance`),
            ]);
            setSummary(await summaryRes.json());
            setHealth(await healthRes.json());
            setVideos(await videosRes.json());
            setWsBalance(await balanceRes.json());
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        // Auto-refresh every 60 seconds
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const handleTestAlert = async () => {
        setAlerting(true);
        try {
            await apiFetch(`${API_V1_BASE_URL}/analytics/alert/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: 'Test Alert',
                    message: 'This is a test alert from AI Video Factory Dashboard.',
                    level: 'info',
                }),
            });
            setSuccess(t('dashboard.testAlertSent'));
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setAlerting(false);
        }
    };

    const handleHealthAlert = async () => {
        try {
            await apiFetch(`${API_V1_BASE_URL}/analytics/health/check-and-alert`, { method: 'POST' });
            setSuccess(t('dashboard.healthCheckDone'));
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        }
    };

    const formatNumber = (n: number) => {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return n.toString();
    };

    return (
        <div className="min-h-screen bg-[var(--background)] text-white">
            {/* Header */}
            <div className="border-b border-white/[0.06] bg-[var(--surface-1)]/70 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/" className="text-gray-400 hover:text-white transition-colors">
                            <ArrowLeft className="w-5 h-5" />
                        </Link>
                        <div>
                            <div className="font-mono text-[9px] uppercase tracking-[0.35em] text-[var(--brand-1)]">● {t('sidebar.dashboard')}</div>
                            <h1 className={`${display.className} text-lg font-bold text-white leading-tight`}>{t('dashboard.title')}</h1>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button
                            onClick={handleTestAlert}
                            disabled={alerting}
                            className="bg-gray-700 hover:bg-gray-600 px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                        >
                            {alerting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Bell className="w-3 h-3" />}
                            {t('dashboard.testAlert')}
                        </button>
                        <button
                            onClick={fetchData}
                            disabled={loading}
                            className="bg-teal-600 hover:bg-teal-700 px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                        >
                            {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                            {t('dashboard.refresh')}
                        </button>
                        <LanguageSwitcher />
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
                {error && (
                    <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg">
                        {error}
                        <button onClick={() => setError('')} className="ml-2">&times;</button>
                    </div>
                )}
                {success && (
                    <div className="bg-green-500/20 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg">
                        {success}
                        <button onClick={() => setSuccess('')} className="ml-2">&times;</button>
                    </div>
                )}

                {/* System Health */}
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-sm font-medium flex items-center gap-2">
                            <Activity className="w-4 h-4 text-teal-400" />
                            {t('dashboard.systemHealth')}
                        </h2>
                        {health && (
                            <span className={`text-xs px-2 py-1 rounded-full ${
                                health.overall ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}>
                                {health.overall ? t('dashboard.allOperational') : t('dashboard.issuesDetected')}
                            </span>
                        )}
                    </div>
                    {health ? (
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                            {/* Redis */}
                            <div className={`rounded-lg p-3 border ${health.redis.healthy ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Database className="w-4 h-4" />
                                    <span className="text-xs font-medium">{t('dashboard.redis')}</span>
                                    {health.redis.healthy ? <CheckCircle className="w-3 h-3 text-green-400 ml-auto" /> : <XCircle className="w-3 h-3 text-red-400 ml-auto" />}
                                </div>
                                <p className="text-[10px] text-gray-400">
                                    {health.redis.healthy ? t('dashboard.memory', { value: health.redis.used_memory_human || '' }) : health.redis.error}
                                </p>
                            </div>
                            {/* Worker */}
                            <div className={`rounded-lg p-3 border ${health.worker.healthy ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Server className="w-4 h-4" />
                                    <span className="text-xs font-medium">{t('dashboard.worker')}</span>
                                    {health.worker.healthy ? <CheckCircle className="w-3 h-3 text-green-400 ml-auto" /> : <XCircle className="w-3 h-3 text-red-400 ml-auto" />}
                                </div>
                                <p className="text-[10px] text-gray-400">
                                    {health.worker.healthy ? t('dashboard.workerActive', { count: health.worker.worker_count || 0 }) : t('dashboard.noWorkers')}
                                </p>
                            </div>
                            {/* API Keys */}
                            <div className={`rounded-lg p-3 border ${health.api_keys.healthy ? 'border-green-500/30 bg-green-500/5' : 'border-yellow-500/30 bg-yellow-500/5'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Key className="w-4 h-4" />
                                    <span className="text-xs font-medium">{t('dashboard.apiKeys')}</span>
                                    {health.api_keys.healthy ? <CheckCircle className="w-3 h-3 text-green-400 ml-auto" /> : <AlertTriangle className="w-3 h-3 text-yellow-400 ml-auto" />}
                                </div>
                                <p className="text-[10px] text-gray-400">{t('dashboard.configured', { count: health.api_keys.configured_count })}</p>
                            </div>
                            {/* YouTube Quota */}
                            <div className={`rounded-lg p-3 border ${health.youtube_quota.healthy ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Youtube className="w-4 h-4" />
                                    <span className="text-xs font-medium">{t('dashboard.ytQuota')}</span>
                                    {health.youtube_quota.healthy ? <CheckCircle className="w-3 h-3 text-green-400 ml-auto" /> : <XCircle className="w-3 h-3 text-red-400 ml-auto" />}
                                </div>
                                <p className="text-[10px] text-gray-400">
                                    {health.youtube_quota.remaining !== undefined
                                        ? t('dashboard.ytQuotaLeft', { remaining: health.youtube_quota.remaining?.toLocaleString() || '0', uploads: health.youtube_quota.max_uploads_remaining || 0 })
                                        : t('dashboard.na')
                                    }
                                </p>
                            </div>
                            {/* WaveSpeed balance */}
                            <div className={`rounded-lg p-3 border ${
                                !wsBalance?.configured ? 'border-gray-500/30 bg-gray-500/5'
                                : (wsBalance.balance ?? 0) >= 5 ? 'border-green-500/30 bg-green-500/5'
                                : 'border-yellow-500/30 bg-yellow-500/5'
                            }`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Zap className="w-4 h-4" />
                                    <span className="text-xs font-medium">{t('dashboard.wsBalance')}</span>
                                    {!wsBalance?.configured ? <AlertTriangle className="w-3 h-3 text-gray-400 ml-auto" />
                                        : (wsBalance.balance ?? 0) >= 5 ? <CheckCircle className="w-3 h-3 text-green-400 ml-auto" />
                                        : <AlertTriangle className="w-3 h-3 text-yellow-400 ml-auto" />}
                                </div>
                                <p className="text-[10px] text-gray-400">
                                    {wsBalance?.configured && wsBalance.balance != null
                                        ? `$${wsBalance.balance.toFixed(2)}`
                                        : t('dashboard.na')}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="flex items-center justify-center py-6">
                            <Loader2 className="w-6 h-6 animate-spin text-teal-400" />
                        </div>
                    )}
                </div>

                {/* Analytics Summary */}
                {summary && (
                    <div>
                        <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
                            <TrendingUp className="w-4 h-4 text-teal-400" />
                            {t('dashboard.videoPerformance')}
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <Eye className="w-5 h-5 text-blue-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{formatNumber(summary.total_views)}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.totalViews')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <ThumbsUp className="w-5 h-5 text-green-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{formatNumber(summary.total_likes)}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.totalLikes')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <MessageCircle className="w-5 h-5 text-yellow-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{formatNumber(summary.total_comments)}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.comments')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <Users className="w-5 h-5 text-teal-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">+{formatNumber(summary.total_subscriber_gain)}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.subscribersGained')}</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <Zap className="w-5 h-5 text-orange-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{summary.total_videos}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.videosPublished')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <Eye className="w-5 h-5 text-cyan-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{formatNumber(Math.round(summary.avg_views_per_video))}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.avgViewsVideo')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <Clock className="w-5 h-5 text-pink-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{formatNumber(Math.round(summary.total_watch_time_minutes))}</p>
                                <p className="text-xs text-gray-400">{t('dashboard.watchTime')}</p>
                            </div>
                            <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
                                <BarChart3 className="w-5 h-5 text-teal-400 mx-auto mb-2" />
                                <p className="text-2xl font-bold">{summary.avg_ctr.toFixed(1)}%</p>
                                <p className="text-xs text-gray-400">{t('dashboard.avgCTR')}</p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Video Analytics Table */}
                <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                    <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
                        <BarChart3 className="w-4 h-4 text-teal-400" />
                        {t('dashboard.videoAnalytics', { count: videos.length })}
                    </h2>
                    {videos.length === 0 ? (
                        <p className="text-gray-500 text-sm text-center py-10">
                            {t('dashboard.noAnalytics')}
                        </p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs">
                                <thead>
                                    <tr className="text-gray-400 border-b border-gray-700">
                                        <th className="text-left py-2 px-2">{t('dashboard.videoId')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.views')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.likes')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.commentsCol')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.watchTimeCol')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.avgDuration')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.ctr')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.subsPlus')}</th>
                                        <th className="text-right py-2 px-2">{t('dashboard.fetched')}</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {videos.map(v => (
                                        <tr key={v.id} className="border-b border-gray-800 hover:bg-gray-700/20">
                                            <td className="py-2 px-2">
                                                <a href={`https://youtube.com/watch?v=${v.youtube_video_id}`}
                                                   target="_blank" rel="noopener noreferrer"
                                                   className="text-teal-400 hover:text-teal-300">
                                                    {v.youtube_video_id}
                                                </a>
                                            </td>
                                            <td className="text-right py-2 px-2">{formatNumber(v.views)}</td>
                                            <td className="text-right py-2 px-2">{formatNumber(v.likes)}</td>
                                            <td className="text-right py-2 px-2">{formatNumber(v.comments)}</td>
                                            <td className="text-right py-2 px-2">{v.watch_time_minutes.toFixed(0)}m</td>
                                            <td className="text-right py-2 px-2">{v.average_view_duration_seconds.toFixed(0)}s</td>
                                            <td className="text-right py-2 px-2">{v.click_through_rate.toFixed(1)}%</td>
                                            <td className="text-right py-2 px-2 text-green-400">+{v.subscriber_gain}</td>
                                            <td className="text-right py-2 px-2 text-gray-500">
                                                {v.fetched_at ? new Date(v.fetched_at).toLocaleDateString() : '-'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>

                {/* Quick Navigation */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Link href="/generate" className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center hover:border-teal-500/50 transition-colors">
                        <Zap className="w-6 h-6 text-teal-400 mx-auto mb-2" />
                        <p className="text-sm font-medium">{t('dashboard.generate')}</p>
                    </Link>
                    <Link href="/trends" className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center hover:border-teal-500/50 transition-colors">
                        <TrendingUp className="w-6 h-6 text-pink-400 mx-auto mb-2" />
                        <p className="text-sm font-medium">{t('dashboard.trends')}</p>
                    </Link>
                    <Link href="/youtube" className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center hover:border-teal-500/50 transition-colors">
                        <Youtube className="w-6 h-6 text-red-400 mx-auto mb-2" />
                        <p className="text-sm font-medium">{t('dashboard.youtubeNav')}</p>
                    </Link>
                    <button
                        onClick={handleHealthAlert}
                        className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center hover:border-teal-500/50 transition-colors"
                    >
                        <Bell className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
                        <p className="text-sm font-medium">{t('dashboard.runHealthCheck')}</p>
                    </button>
                </div>
            </div>
        </div>
    );
}
