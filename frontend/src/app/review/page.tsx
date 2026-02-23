'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
    CheckCircle, XCircle, Upload, RefreshCw, Eye, Loader2,
    ArrowLeft, Tag, Zap, Calendar, Play, Globe
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { safeStringArray } from '@/lib/safeJson';
import { toErrorMessage } from '@/lib/errorUtils';
import { API_V1_BASE_URL } from '@/lib/apiBase';

interface ReviewItem {
    id: number;
    story_idea_id: number | null;
    project_id: number | null;
    video_url: string;
    title: string;
    description: string;
    tags_json: string;
    status: string;
    reviewer_notes: string;
    created_at: string;
    genre: string | null;
    virality_score: number | null;
    idea_text: string | null;
}

interface ReviewApprovePayload {
    title?: string;
    description?: string;
    tags?: string[];
}

interface ReviewSchedulePayload extends ReviewApprovePayload {
    scheduled_publish_at: string;
}

export default function ReviewPage() {
    const { t } = useLanguage();
    const [items, setItems] = useState<ReviewItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<number | null>(null);
    const [statusFilter, setStatusFilter] = useState('');
    const [error, setError] = useState('');
    const [editingItem, setEditingItem] = useState<number | null>(null);
    const [editTitle, setEditTitle] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [editTags, setEditTags] = useState('');
    const [scheduleDate, setScheduleDate] = useState('');

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        try {
            let url = `${API_V1_BASE_URL}/review/queue?limit=50`;
            if (statusFilter) url += `&status=${statusFilter}`;
            const res = await fetch(url);
            const data = await res.json();
            setItems(data);
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => {
        fetchQueue();
    }, [fetchQueue]);

    const startEditing = (item: ReviewItem) => {
        setEditingItem(item.id);
        setEditTitle(item.title);
        setEditDescription(item.description);
        const tags = safeStringArray(item.tags_json);
        setEditTags(tags.join(', '));
        setScheduleDate('');
    };

    const cancelEditing = () => {
        setEditingItem(null);
    };

    const handleApprove = async (itemId: number) => {
        setActionLoading(itemId);
        setError('');
        try {
            const body: ReviewApprovePayload = {};
            if (editingItem === itemId) {
                body.title = editTitle;
                body.description = editDescription;
                body.tags = editTags.split(',').map(tag => tag.trim()).filter(Boolean);
            }
            const res = await fetch(`${API_V1_BASE_URL}/review/${itemId}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Approve failed');
            setEditingItem(null);
            await fetchQueue();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setActionLoading(null);
        }
    };

    const handleSchedule = async (itemId: number) => {
        if (!scheduleDate) {
            setError(t('review.errorSchedule'));
            return;
        }
        setActionLoading(itemId);
        setError('');
        try {
            const body: ReviewSchedulePayload = {
                scheduled_publish_at: new Date(scheduleDate).toISOString(),
            };
            if (editingItem === itemId) {
                body.title = editTitle;
                body.description = editDescription;
                body.tags = editTags.split(',').map(tag => tag.trim()).filter(Boolean);
            }
            const res = await fetch(`${API_V1_BASE_URL}/review/${itemId}/schedule`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Schedule failed');
            setEditingItem(null);
            await fetchQueue();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setActionLoading(null);
        }
    };

    const handleReject = async (itemId: number) => {
        setActionLoading(itemId);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/review/${itemId}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Reject failed');
            await fetchQueue();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setActionLoading(null);
        }
    };

    const handleRegenerate = async (itemId: number) => {
        setActionLoading(itemId);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/review/${itemId}/regenerate`, {
                method: 'POST',
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Regenerate failed');
            await fetchQueue();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setActionLoading(null);
        }
    };

    const handlePublish = async (itemId: number) => {
        setActionLoading(itemId);
        setError('');
        try {
            const res = await fetch(`${API_V1_BASE_URL}/review/${itemId}/publish`, {
                method: 'POST',
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Publish failed');
            await fetchQueue();
        } catch (e: unknown) {
            setError(toErrorMessage(e));
        } finally {
            setActionLoading(null);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'pending_review': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            case 'approved': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
            case 'rejected': return 'bg-red-500/20 text-red-400 border-red-500/30';
            case 'uploaded': return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'published': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
            default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    const getGenreEmoji = (genre: string | null) => {
        if (!genre) return '';
        const map: Record<string, string> = {
            drama: '', comedy: '', horror: '', thriller: '',
            romance: '', 'sci-fi': '', mystery: '',
        };
        return map[genre] || '';
    };

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
                            <Eye className="w-6 h-6 text-orange-400" />
                            {t('review.title')}
                        </h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value)}
                            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
                        >
                            <option value="">{t('review.allStatuses')}</option>
                            <option value="pending_review">{t('review.pendingReview')}</option>
                            <option value="approved">{t('review.approved')}</option>
                            <option value="uploaded">{t('review.uploadedPrivate')}</option>
                            <option value="published">{t('review.published')}</option>
                            <option value="rejected">{t('review.rejected')}</option>
                        </select>
                        <button
                            onClick={fetchQueue}
                            className="bg-gray-700 hover:bg-gray-600 px-3 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors"
                        >
                            <RefreshCw className="w-4 h-4" /> {t('review.refresh')}
                        </button>
                        <LanguageSwitcher />
                    </div>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-6">
                {error && (
                    <div className="bg-red-500/20 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-4">
                        {error}
                        <button onClick={() => setError('')} className="ml-4 text-red-300 hover:text-white">x</button>
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-center py-20 text-gray-500">
                        <Eye className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-lg">{t('review.noVideos')}</p>
                        <p className="text-sm mt-2">
                            {t('review.noVideosHint')} <Link href="/trends" className="text-purple-400 hover:text-purple-300">{t('review.trendsLink')}</Link>
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {items.map((item) => {
                            const tags = safeStringArray(item.tags_json);
                            const isEditing = editingItem === item.id;
                            const isLoading = actionLoading === item.id;

                            return (
                                <div key={item.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-5 hover:border-purple-500/30 transition-colors">
                                    <div className="flex flex-col lg:flex-row gap-5">
                                        {/* Video Preview */}
                                        <div className="lg:w-64 flex-shrink-0">
                                            {item.video_url ? (
                                                <video
                                                    src={item.video_url}
                                                    controls
                                                    className="w-full aspect-[9/16] max-h-80 rounded-lg bg-black object-contain"
                                                    preload="metadata"
                                                />
                                            ) : (
                                                <div className="w-full aspect-[9/16] max-h-80 rounded-lg bg-gray-700/50 flex items-center justify-center">
                                                    <Play className="w-8 h-8 text-gray-500" />
                                                </div>
                                            )}
                                        </div>

                                        {/* Details */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-3 flex-wrap">
                                                <span className={`text-xs px-2 py-0.5 rounded-full border ${getStatusColor(item.status)}`}>
                                                    {item.status.replace('_', ' ')}
                                                </span>
                                                {item.genre && (
                                                    <span className="text-xs text-purple-400 uppercase font-medium">
                                                        {getGenreEmoji(item.genre)} {item.genre}
                                                    </span>
                                                )}
                                                {item.virality_score != null && (
                                                    <span className="text-xs text-yellow-400 flex items-center gap-1">
                                                        <Zap className="w-3 h-3" />
                                                        {(item.virality_score * 100).toFixed(0)}%
                                                    </span>
                                                )}
                                                <span className="text-xs text-gray-500 ml-auto">
                                                    #{item.id} &middot; {new Date(item.created_at).toLocaleDateString()}
                                                </span>
                                            </div>

                                            {item.idea_text && (
                                                <p className="text-xs text-gray-500 mb-2 italic line-clamp-2">
                                                    {t('review.idea')}{item.idea_text}
                                                </p>
                                            )}

                                            {/* Editable fields */}
                                            {isEditing ? (
                                                <div className="space-y-3">
                                                    <div>
                                                        <label className="text-xs text-gray-400 mb-1 block">{t('review.titleLabel')}</label>
                                                        <input
                                                            type="text"
                                                            value={editTitle}
                                                            onChange={(e) => setEditTitle(e.target.value)}
                                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                                            maxLength={100}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-gray-400 mb-1 block">{t('review.descriptionLabel')}</label>
                                                        <textarea
                                                            value={editDescription}
                                                            onChange={(e) => setEditDescription(e.target.value)}
                                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm h-24 resize-none"
                                                            maxLength={5000}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-gray-400 mb-1 block">{t('review.tagsLabel')}</label>
                                                        <input
                                                            type="text"
                                                            value={editTags}
                                                            onChange={(e) => setEditTags(e.target.value)}
                                                            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-gray-400 mb-1 block">{t('review.scheduleLabel')}</label>
                                                        <input
                                                            type="datetime-local"
                                                            value={scheduleDate}
                                                            onChange={(e) => setScheduleDate(e.target.value)}
                                                            className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm"
                                                        />
                                                    </div>
                                                </div>
                                            ) : (
                                                <>
                                                    <h3 className="font-medium text-base mb-1">{item.title || t('review.untitled')}</h3>
                                                    <p className="text-sm text-gray-400 mb-2 line-clamp-3">{item.description}</p>
                                                    {tags.length > 0 && (
                                                        <div className="flex flex-wrap gap-1 mb-2">
                                                            {tags.slice(0, 8).map((tag: string, i: number) => (
                                                                <span key={i} className="text-[10px] bg-gray-700/50 text-gray-400 px-1.5 py-0.5 rounded flex items-center gap-1">
                                                                    <Tag className="w-2.5 h-2.5" />{tag}
                                                                </span>
                                                            ))}
                                                            {tags.length > 8 && (
                                                                <span className="text-[10px] text-gray-500">+{tags.length - 8} more</span>
                                                            )}
                                                        </div>
                                                    )}
                                                </>
                                            )}

                                            {item.reviewer_notes && (
                                                <p className="text-xs text-gray-500 mt-2 border-t border-gray-700 pt-2">
                                                    {t('review.notes')}{item.reviewer_notes}
                                                </p>
                                            )}

                                            {/* Actions */}
                                            <div className="flex flex-wrap gap-2 mt-4">
                                                {item.status === 'pending_review' && (
                                                    <>
                                                        {!isEditing ? (
                                                            <button
                                                                onClick={() => startEditing(item)}
                                                                className="bg-gray-600 hover:bg-gray-500 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                                                            >
                                                                {t('review.edit')}
                                                            </button>
                                                        ) : (
                                                            <button
                                                                onClick={cancelEditing}
                                                                className="bg-gray-600 hover:bg-gray-500 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                                                            >
                                                                {t('review.cancel')}
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleApprove(item.id)}
                                                            disabled={isLoading}
                                                            className="bg-green-600 hover:bg-green-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                        >
                                                            {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
                                                            {t('review.approveUpload')}
                                                        </button>
                                                        {isEditing && scheduleDate && (
                                                            <button
                                                                onClick={() => handleSchedule(item.id)}
                                                                disabled={isLoading}
                                                                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                            >
                                                                {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Calendar className="w-3 h-3" />}
                                                                {t('review.schedule')}
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleReject(item.id)}
                                                            disabled={isLoading}
                                                            className="bg-red-600/50 hover:bg-red-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                        >
                                                            <XCircle className="w-3 h-3" /> {t('review.reject')}
                                                        </button>
                                                        <button
                                                            onClick={() => handleRegenerate(item.id)}
                                                            disabled={isLoading}
                                                            className="bg-orange-600/50 hover:bg-orange-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                        >
                                                            <RefreshCw className="w-3 h-3" /> {t('review.regenerate')}
                                                        </button>
                                                    </>
                                                )}
                                                {item.status === 'uploaded' && (
                                                    <button
                                                        onClick={() => handlePublish(item.id)}
                                                        disabled={isLoading}
                                                        className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 px-4 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                    >
                                                        {isLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Globe className="w-3 h-3" />}
                                                        {t('review.publishAction')}
                                                    </button>
                                                )}
                                                {item.status === 'rejected' && (
                                                    <>
                                                        <button
                                                            onClick={() => handleRegenerate(item.id)}
                                                            disabled={isLoading}
                                                            className="bg-orange-600/50 hover:bg-orange-600 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1 transition-colors"
                                                        >
                                                            <RefreshCw className="w-3 h-3" /> {t('review.regenerate')}
                                                        </button>
                                                        <button
                                                            onClick={() => { startEditing(item); }}
                                                            className="bg-gray-600 hover:bg-gray-500 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                                                        >
                                                            {t('review.editReapprove')}
                                                        </button>
                                                    </>
                                                )}
                                                {item.status === 'published' && (
                                                    <span className="text-xs text-green-400 flex items-center gap-1">
                                                        <CheckCircle className="w-3 h-3" /> {t('review.publishedOnYT')}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
