'use client';

import { useProjectWebSocket, JobProgress } from '@/lib/useWebSocket';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { useLanguage } from '@/contexts/LanguageContext';

interface ProgressDashboardProps {
    projectId: number | string;
}

const jobTypeIcons: Record<string, string> = {
    'GENERATE_STORY': '📖',
    'GENERATE_SCENES': '🎬',
    'GENERATE_SCENE_PROMPTS': '✍️',
    'GENERATE_SCENE_MEDIA': '🎥',
    'RENDER_EPISODE': '🎞️',
    'QUALITY_CHECK': '✅',
};

const statusStyles: Record<string, string> = {
    queued: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
    in_progress: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    done: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
};

function JobCard({ job }: { job: JobProgress }) {
    const { t } = useLanguage();

    const typeLabels: Record<string, string> = {
        'GENERATE_STORY': t('progress.generatingStory'),
        'GENERATE_SCENES': t('progress.creatingScenes'),
        'GENERATE_SCENE_PROMPTS': t('progress.writingPrompts'),
        'GENERATE_SCENE_MEDIA': t('progress.generatingVideo'),
        'RENDER_EPISODE': t('progress.renderingEpisode'),
        'QUALITY_CHECK': t('progress.qualityCheck'),
    };

    const icon = jobTypeIcons[job.type] || '⚙️';
    const label = typeLabels[job.type] || job.type;
    const statusStyle = statusStyles[job.status] || statusStyles.queued;

    return (
        <div className="border rounded-lg p-4 bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-xl">{icon}</span>
                    <span className="font-medium text-sm">{label}</span>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${statusStyle}`}>
                    {job.status.replace('_', ' ')}
                </span>
            </div>

            {job.status === 'in_progress' && (
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-2 overflow-hidden">
                    <div
                        className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${job.progress}%` }}
                    />
                </div>
            )}

            {job.episode_id && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                    {t('progress.episode', { id: job.episode_id })}
                </p>
            )}

            {job.error_text && (
                <p className="text-xs text-red-500 mt-1 truncate" title={job.error_text}>
                    {t('progress.error', { text: job.error_text })}
                </p>
            )}
        </div>
    );
}

function ConnectionIndicator({ status }: { status: string }) {
    const { t } = useLanguage();

    const statusConfig: Record<string, { color: string; text: string }> = {
        connected: { color: 'bg-green-500', text: t('progress.live') },
        connecting: { color: 'bg-yellow-500 animate-pulse', text: t('progress.connecting') },
        disconnected: { color: 'bg-gray-400', text: t('progress.offline') },
        error: { color: 'bg-red-500', text: t('progress.errorStatus') },
    };

    const config = statusConfig[status] || statusConfig.disconnected;

    return (
        <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${config.color}`} />
            <span className="text-xs text-gray-500 dark:text-gray-400">{config.text}</span>
        </div>
    );
}

export default function ProgressDashboard({ projectId }: ProgressDashboardProps) {
    const { t } = useLanguage();
    const { isConnected, jobsList, connectionStatus } = useProjectWebSocket(projectId);
    const [initialJobs, setInitialJobs] = useState<JobProgress[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Fetch initial jobs on mount
    useEffect(() => {
        const fetchJobs = async () => {
            try {
                const response = await api.get(`/jobs/project/${projectId}`);
                setInitialJobs(response.data);
            } catch (error) {
                console.error('Failed to fetch jobs:', error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchJobs();
    }, [projectId]);

    // Merge WebSocket updates with initial jobs
    const allJobs = new Map<number, JobProgress>();
    initialJobs.forEach(job => allJobs.set(job.id, job));
    jobsList.forEach(job => allJobs.set(job.id, job));

    const jobs = Array.from(allJobs.values()).sort((a, b) => b.id - a.id);

    const activeJobs = jobs.filter(j => j.status === 'in_progress');
    const queuedJobs = jobs.filter(j => j.status === 'queued');
    const completedJobs = jobs.filter(j => j.status === 'done');
    const failedJobs = jobs.filter(j => j.status === 'failed');

    const totalJobs = jobs.length;
    const completedCount = completedJobs.length;
    const overallProgress = totalJobs > 0 ? Math.round((completedCount / totalJobs) * 100) : 0;

    if (isLoading) {
        return (
            <div className="animate-pulse space-y-4">
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
                <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
                <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded"></div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header with connection status */}
            <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold">{t('progress.title')}</h3>
                <ConnectionIndicator status={connectionStatus} />
            </div>

            {/* Overall progress bar */}
            {totalJobs > 0 && (
                <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-4">
                    <div className="flex justify-between text-sm mb-2">
                        <span className="font-medium">{t('progress.overallProgress')}</span>
                        <span className="text-gray-500">{t('progress.tasks', { completed: completedCount, total: totalJobs })}</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                        <div
                            className="bg-gradient-to-r from-green-400 to-green-600 h-3 rounded-full transition-all duration-700 ease-out"
                            style={{ width: `${overallProgress}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Active jobs */}
            {activeJobs.length > 0 && (
                <div>
                    <h4 className="font-bold mb-3 flex items-center gap-2">
                        <span className="animate-spin">🔄</span> {t('progress.inProgress', { count: activeJobs.length })}
                    </h4>
                    <div className="grid gap-3">
                        {activeJobs.map(job => <JobCard key={job.id} job={job} />)}
                    </div>
                </div>
            )}

            {/* Queued jobs */}
            {queuedJobs.length > 0 && (
                <div>
                    <h4 className="font-bold mb-3 text-gray-600 dark:text-gray-400">
                        ⏳ {t('progress.queued', { count: queuedJobs.length })}
                    </h4>
                    <div className="grid gap-2 opacity-70">
                        {queuedJobs.slice(0, 5).map(job => <JobCard key={job.id} job={job} />)}
                        {queuedJobs.length > 5 && (
                            <p className="text-sm text-gray-500 text-center">
                                {t('progress.moreInQueue', { count: queuedJobs.length - 5 })}
                            </p>
                        )}
                    </div>
                </div>
            )}

            {/* Failed jobs */}
            {failedJobs.length > 0 && (
                <div>
                    <h4 className="font-bold mb-3 text-red-600">
                        ❌ {t('progress.failed', { count: failedJobs.length })}
                    </h4>
                    <div className="grid gap-2">
                        {failedJobs.map(job => <JobCard key={job.id} job={job} />)}
                    </div>
                </div>
            )}

            {/* Completed jobs (collapsed) */}
            {completedJobs.length > 0 && (
                <details className="group">
                    <summary className="cursor-pointer font-bold mb-3 text-green-600 dark:text-green-400 list-none flex items-center gap-2">
                        <span className="transition-transform group-open:rotate-90">▶</span>
                        ✅ {t('progress.completed', { count: completedJobs.length })}
                    </summary>
                    <div className="grid gap-2 mt-3 opacity-60">
                        {completedJobs.slice(0, 10).map(job => <JobCard key={job.id} job={job} />)}
                        {completedJobs.length > 10 && (
                            <p className="text-sm text-gray-500 text-center">
                                {t('progress.moreCompleted', { count: completedJobs.length - 10 })}
                            </p>
                        )}
                    </div>
                </details>
            )}

            {/* Empty state */}
            {jobs.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                    <p className="text-4xl mb-2">📋</p>
                    <p>{t('progress.noTasks')}</p>
                </div>
            )}
        </div>
    );
}
