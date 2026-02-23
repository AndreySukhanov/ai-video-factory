'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
    Youtube, Link2, Upload, Clock, Trash2, Loader2,
    ArrowLeft, CheckCircle, XCircle, AlertTriangle, BarChart3
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { toErrorMessage } from '@/lib/errorUtils';
import { API_V1_BASE_URL } from '@/lib/apiBase';

interface YouTubeChannel {
    id: number;
    channel_id: string;
    channel_title: string;
    is_active: boolean;
    created_at: string;
}

interface YouTubeUploadItem {
    id: number;
    channel_id: number;
    project_id: number | null;
    youtube_video_id: string | null;
    title: string;
    description: string;
    status: string;
    privacy_status: string;
    scheduled_publish_at: string | null;
    published_at: string | null;
    youtube_url: string | null;
    error_text: string | null;
    created_at: string;
}

interface QuotaStatus {
    daily_limit: number;
    used: number;
    remaining: number;
    upload_cost: number;
    max_uploads_remaining: number;
    date: string;
}

export default function YouTubePage() {
    const { t } = useLanguage();
    const [channels, setChannels] = useState<YouTubeChannel[]>([]);
    const [uploads, setUploads] = useState<YouTubeUploadItem[]>([]);
    const [quota, setQuota] = useState<QuotaStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    // Upload form state
    const [uploadForm, setUploadForm] = useState({
        channel_id: 0,
        video_url: '',
        title: '',
        description: '',
        tags: '',
        privacy_status: 'private',
        generate_metadata: false,
        story_idea_text: '',
    });

    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            const [channelsRes, uploadsRes, quotaRes] = await Promise.all([
                fetch(`${API_V1_BASE_URL}/youtube/channels`),
                fetch(`${API_V1_BASE_URL}/youtube/uploads?limit=50`),
                fetch(`${API_V1_BASE_URL}/youtube/quota`),
            ]);
            setChannels(await channelsRes.json());
            setUploads(await uploadsRes.json());
            setQuota(await quotaRes.json());
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        // Check for auth callback params
        const params = new URLSearchParams(window.location.search);
        if (params.get('auth') === 'success') {
            setSuccess(t('youtube.authSuccess'));
            window.history.replaceState({}, '', '/youtube');
        } else if (params.get('auth') === 'error') {
            setError(`Auth failed: ${params.get('message') || 'Unknown error'}`);
            window.history.replaceState({}, '', '/youtube');
        }
    }, [fetchData, t]);

    const handleConnect = async () => {
        try {
            const res = await fetch(`${API_V1_BASE_URL}/youtube/auth/url`);
            const data = await res.json().catch(() => ({} as Record<string, unknown>));

            if (!res.ok) {
                const detail = typeof data.detail === 'string'
                    ? data.detail
                    : 'Failed to get YouTube auth URL';
                throw new Error(detail);
            }

            if (typeof data.auth_url !== 'string' || !data.auth_url) {
                throw new Error('YouTube auth URL is missing in server response');
            }

            window.location.href = data.auth_url;
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        }
    };

    const handleDisconnect = async (channelId: number) => {
        try {
            await fetch(`${API_V1_BASE_URL}/youtube/channels/${channelId}`, { method: 'DELETE' });
            await fetchData();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        }
    };

    const handleUpload = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!uploadForm.channel_id || !uploadForm.video_url) {
            setError(t('youtube.errorChannelRequired'));
            return;
        }
        setUploading(true);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/youtube/upload`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...uploadForm,
                    tags: uploadForm.tags.split(',').map(tag => tag.trim()).filter(Boolean),
                }),
            });
            const data = await res.json();
            if (res.ok) {
                setSuccess(t('youtube.videoUploaded', { url: data.youtube_url || '' }));
                setUploadForm(prev => ({ ...prev, video_url: '', title: '', description: '', tags: '' }));
                await fetchData();
            } else {
                setError(data.detail || 'Upload failed');
            }
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setUploading(false);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'published': return <CheckCircle className="w-4 h-4 text-green-400" />;
            case 'scheduled': return <Clock className="w-4 h-4 text-blue-400" />;
            case 'uploading': return <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />;
            case 'failed': return <XCircle className="w-4 h-4 text-red-400" />;
            default: return <Clock className="w-4 h-4 text-gray-400" />;
        }
    };

    const quotaPercent = quota ? (quota.used / quota.daily_limit) * 100 : 0;

    return (
        <div className="min-h-screen bg-[var(--background)] text-white">
            {/* Header */}
            <div className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/" className="text-gray-400 hover:text-white transition-colors">
                            <ArrowLeft className="w-5 h-5" />
                        </Link>
                        <h1 className="text-xl font-bold flex items-center gap-2">
                            <Youtube className="w-6 h-6 text-red-500" />
                            {t('youtube.title')}
                        </h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <LanguageSwitcher />
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
                {error && (
                    <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" /> {error}
                        <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-300">&times;</button>
                    </div>
                )}
                {success && (
                    <div className="bg-green-500/20 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg flex items-center gap-2">
                        <CheckCircle className="w-4 h-4" /> {success}
                        <button onClick={() => setSuccess('')} className="ml-auto text-green-400 hover:text-green-300">&times;</button>
                    </div>
                )}

                {/* Quota Meter */}
                {quota && (
                    <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-2">
                            <h2 className="text-sm font-medium flex items-center gap-2">
                                <BarChart3 className="w-4 h-4 text-purple-400" />
                                {t('youtube.apiQuota')}
                            </h2>
                            <span className="text-xs text-gray-400">
                                {t('youtube.units', { used: quota.used.toLocaleString(), limit: quota.daily_limit.toLocaleString(), uploads: quota.max_uploads_remaining })}
                            </span>
                        </div>
                        <div className="w-full bg-gray-700 rounded-full h-2">
                            <div
                                className={`h-2 rounded-full transition-all ${
                                    quotaPercent > 80 ? 'bg-red-500' : quotaPercent > 50 ? 'bg-yellow-500' : 'bg-green-500'
                                }`}
                                style={{ width: `${Math.min(quotaPercent, 100)}%` }}
                            />
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left: Channels + Upload Form */}
                    <div className="lg:col-span-1 space-y-6">
                        {/* Channels */}
                        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                            <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
                                <Link2 className="w-4 h-4 text-purple-400" />
                                {t('youtube.connectedChannels')}
                            </h2>
                            {channels.length === 0 ? (
                                <p className="text-gray-500 text-sm mb-3">{t('youtube.noChannels')}</p>
                            ) : (
                                <div className="space-y-2 mb-3">
                                    {channels.map(ch => (
                                        <div key={ch.id} className="flex items-center justify-between bg-gray-700/30 rounded-lg px-3 py-2">
                                            <div>
                                                <p className="text-sm font-medium">{ch.channel_title}</p>
                                                <p className="text-xs text-gray-500">{ch.channel_id}</p>
                                            </div>
                                            <button
                                                onClick={() => handleDisconnect(ch.id)}
                                                className="text-red-400 hover:text-red-300"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <button
                                onClick={handleConnect}
                                className="w-full bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                            >
                                <Youtube className="w-4 h-4" />
                                {t('youtube.connectChannel')}
                            </button>
                        </div>

                        {/* Upload Form */}
                        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                            <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
                                <Upload className="w-4 h-4 text-purple-400" />
                                {t('youtube.uploadVideo')}
                            </h2>
                            <form onSubmit={handleUpload} className="space-y-3">
                                <select
                                    value={uploadForm.channel_id}
                                    onChange={e => setUploadForm(prev => ({ ...prev, channel_id: Number(e.target.value) }))}
                                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                >
                                    <option value={0}>{t('youtube.selectChannel')}</option>
                                    {channels.map(ch => (
                                        <option key={ch.id} value={ch.id}>{ch.channel_title}</option>
                                    ))}
                                </select>
                                <input
                                    type="text"
                                    placeholder={t('youtube.videoUrl')}
                                    value={uploadForm.video_url}
                                    onChange={e => setUploadForm(prev => ({ ...prev, video_url: e.target.value }))}
                                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                />
                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        id="generate_meta"
                                        checked={uploadForm.generate_metadata}
                                        onChange={e => setUploadForm(prev => ({ ...prev, generate_metadata: e.target.checked }))}
                                        className="rounded"
                                    />
                                    <label htmlFor="generate_meta" className="text-xs text-gray-400">
                                        {t('youtube.autoGenMeta')}
                                    </label>
                                </div>
                                {uploadForm.generate_metadata && (
                                    <textarea
                                        placeholder={t('youtube.storyContext')}
                                        value={uploadForm.story_idea_text}
                                        onChange={e => setUploadForm(prev => ({ ...prev, story_idea_text: e.target.value }))}
                                        className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm h-16 resize-none"
                                    />
                                )}
                                {!uploadForm.generate_metadata && (
                                    <>
                                        <input
                                            type="text"
                                            placeholder={t('youtube.titlePlaceholder')}
                                            value={uploadForm.title}
                                            onChange={e => setUploadForm(prev => ({ ...prev, title: e.target.value }))}
                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                        />
                                        <textarea
                                            placeholder={t('youtube.descriptionPlaceholder')}
                                            value={uploadForm.description}
                                            onChange={e => setUploadForm(prev => ({ ...prev, description: e.target.value }))}
                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm h-16 resize-none"
                                        />
                                        <input
                                            type="text"
                                            placeholder={t('youtube.tagsPlaceholder')}
                                            value={uploadForm.tags}
                                            onChange={e => setUploadForm(prev => ({ ...prev, tags: e.target.value }))}
                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                        />
                                    </>
                                )}
                                <select
                                    value={uploadForm.privacy_status}
                                    onChange={e => setUploadForm(prev => ({ ...prev, privacy_status: e.target.value }))}
                                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                >
                                    <option value="private">{t('youtube.private')}</option>
                                    <option value="unlisted">{t('youtube.unlisted')}</option>
                                    <option value="public">{t('youtube.public')}</option>
                                </select>
                                <button
                                    type="submit"
                                    disabled={uploading || !uploadForm.channel_id || !uploadForm.video_url}
                                    className="w-full bg-gradient-to-r from-red-600 to-pink-600 hover:from-red-700 hover:to-pink-700 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                                >
                                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                                    {uploading ? t('youtube.uploading') : t('youtube.upload')}
                                </button>
                            </form>
                        </div>
                    </div>

                    {/* Right: Uploads List */}
                    <div className="lg:col-span-2">
                        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                            <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
                                <Clock className="w-4 h-4 text-purple-400" />
                                {t('youtube.uploadHistory', { count: uploads.length })}
                            </h2>
                            {loading ? (
                                <div className="flex items-center justify-center py-10">
                                    <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
                                </div>
                            ) : uploads.length === 0 ? (
                                <p className="text-gray-500 text-sm text-center py-10">{t('youtube.noUploads')}</p>
                            ) : (
                                <div className="space-y-2">
                                    {uploads.map(upload => (
                                        <div key={upload.id} className="flex items-center gap-3 bg-gray-700/30 rounded-lg px-4 py-3">
                                            {getStatusIcon(upload.status)}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{upload.title}</p>
                                                <p className="text-xs text-gray-500">
                                                    {upload.status} &middot; {upload.privacy_status}
                                                    {upload.scheduled_publish_at && ` &middot; Scheduled: ${new Date(upload.scheduled_publish_at).toLocaleString()}`}
                                                </p>
                                                {upload.error_text && (
                                                    <p className="text-xs text-red-400 mt-1">{upload.error_text}</p>
                                                )}
                                            </div>
                                            {upload.youtube_url && (
                                                <a
                                                    href={upload.youtube_url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-xs text-red-400 hover:text-red-300 whitespace-nowrap"
                                                >
                                                    {t('youtube.viewOnYT')}
                                                </a>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
