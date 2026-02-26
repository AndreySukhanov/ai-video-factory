'use client';

import { useState, useEffect, useRef, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import ImageUpload from '@/components/ImageUpload';
import {
    Camera, PenLine, Settings, Link2, Film, AlertTriangle,
    Play, Trash2, ChevronUp, ChevronDown, Download, FolderOpen, Sparkles, BookOpen, User, Loader2, CheckCircle, Send
} from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { safeJsonParse, safeStringArray } from '@/lib/safeJson';
import { isUiV2Enabled } from '@/lib/featureFlags';
import GenerationWizardV2 from '@/features/generate-v2/GenerationWizardV2';
import { API_BASE_URL, API_V1_BASE_URL, WS_BASE_URL } from '@/lib/apiBase';

// Progress state interface
interface GenerationProgress {
    stage: string;
    progress: number;
    message: string;
    videoUrl?: string;
}

// Model configurations with constraints
const MODEL_CONFIG = {
    veo3: {
        name: 'Veo 3 Fast',
        durations: [4, 6, 8],
        defaultDuration: 4,
        aspectRatios: ['9:16', '16:9'],
        supportsI2V: true,
        supportsCharacterConsistency: false,
    },
    veo31: {
        name: 'Veo 3.1 (R2V)',
        durations: [8],
        defaultDuration: 8,
        aspectRatios: ['16:9'],
        supportsI2V: true,
        supportsCharacterConsistency: true,
        consistencyNote: 'R2V: 16:9, 8 сек, 1-3 ref',
    },
    kling: {
        name: 'Kling 2.6',
        durations: [5, 10],
        defaultDuration: 5,
        aspectRatios: ['9:16', '16:9', '1:1'],
        supportsI2V: true,
        supportsCharacterConsistency: false,
    },
    minimax: {
        name: 'MiniMax (S2V)',
        durations: [6],
        defaultDuration: 6,
        aspectRatios: ['9:16', '16:9', '1:1'],
        supportsI2V: true,
        supportsCharacterConsistency: true,
        consistencyNote: 'S2V-01: 6 сек',
    },
};

type ModelType = keyof typeof MODEL_CONFIG;

interface GenerationResult {
    success: boolean;
    video_url?: string;
    status: string;
    duration?: number;
    generation_time?: number;
    error?: string;
}

interface Episode {
    id: string;
    prompt: string;
    video_url: string;
    duration: number;
    created_at: string;
}

interface Series {
    id: string;
    name: string;
    episodes: Episode[];
    created_at: string;
}

interface LoadedProject {
    id: number;
    title: string;
    logline: string;
    genre: string;
    total_episodes?: number;
    episode_duration_sec?: number;
    seo_title?: string;
    seo_description?: string;
    seo_tags_json?: string;
    status: string;
    episodes: unknown[];
}

// LocalStorage keys
const SERIES_STORAGE_KEY = 'ai_video_factory_series';
const PROMPTS_STORAGE_KEY = 'ai_video_factory_prompts';

export default function GenerateEpisodePageWrapper() {
    if (isUiV2Enabled) {
        return (
            <Suspense fallback={<div className="min-h-screen bg-gray-900 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-purple-400" /></div>}>
                <GenerationWizardV2 />
            </Suspense>
        );
    }

    return (
        <Suspense fallback={<div className="min-h-screen bg-gray-900 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-purple-400" /></div>}>
            <GenerateEpisodePage />
        </Suspense>
    );
}

function GenerateEpisodePage() {
    const { t } = useLanguage();
    const searchParams = useSearchParams();

    // Mode state
    const [mode, setMode] = useState<'single' | 'batch' | 'story'>('single');

    // Loaded project state
    const [loadedProject, setLoadedProject] = useState<LoadedProject | null>(null);

    // Single mode state
    const [prompt, setPrompt] = useState('');
    const [duration, setDuration] = useState(4);
    const [aspectRatio, setAspectRatio] = useState('9:16');
    const [model, setModel] = useState<ModelType>('veo3');
    const [storyModel, setStoryModel] = useState<'minimax' | 'veo31'>('minimax');
    const [referenceImageUrl, setReferenceImageUrl] = useState<string | null>(null);

    useEffect(() => {
        if (model === 'veo3') {
            if (aspectRatio === '1:1') {
                setAspectRatio('9:16');
            }
            if (referenceImageUrl) {
                setReferenceImageUrl(null);
            }
        }
    }, [model]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [result, setResult] = useState<GenerationResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Send to Review state
    const [sendingToReview, setSendingToReview] = useState(false);
    const [sentToReview, setSentToReview] = useState(false);

    // Batch mode state
    const [batchPrompts, setBatchPrompts] = useState<string[]>(['']);
    const [batchProgress, setBatchProgress] = useState<{ current: number, total: number } | null>(null);

    // Series state
    const [series, setSeries] = useState<Series[]>([]);
    const [currentSeries, setCurrentSeries] = useState<Series | null>(null);
    const [isMerging, setIsMerging] = useState(false);

    // Story Mode state
    const [storyIdea, setStoryIdea] = useState('');
    const [storyGenre, setStoryGenre] = useState('drama');
    const [storyEpisodesCount, setStoryEpisodesCount] = useState(5);
    const [isGeneratingStory, setIsGeneratingStory] = useState(false);
    const [generatedEpisodes, setGeneratedEpisodes] = useState<Array<{
        number: number;
        title: string;
        synopsis: string;
        prompt: string;
    }>>([]);
    const [seriesTitle, setSeriesTitle] = useState('');
    const [seriesLogline, setSeriesLogline] = useState('');

    // Character Consistency state
    const [characterImageUrl, setCharacterImageUrl] = useState<string | null>(null);
    const [characterName, setCharacterName] = useState<string>('');
    const [characterDescription, setCharacterDescription] = useState<string>('');
    const [isConsistencyEnabled, setIsConsistencyEnabled] = useState(true);
    const [veoReferenceImages, setVeoReferenceImages] = useState<string[]>([]);

    // WebSocket progress state
    const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const sessionIdRef = useRef<string>('');

    const generateSessionId = useCallback(() => {
        return `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    }, []);

    const connectWebSocket = useCallback((sessionId: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.close();
        }

        const ws = new WebSocket(`${WS_BASE_URL}/api/v1/ws/session/${sessionId}`);

        ws.onopen = () => {
            console.log('[WS] Connected for progress updates');
        };

        ws.onmessage = (event) => {
            const data = safeJsonParse<Record<string, unknown> | null>(event.data, null);
            if (!data) {
                console.error('[WS] Parse error: invalid payload');
                return;
            }
            if (data.type === 'progress') {
                setGenerationProgress({
                    stage: String(data.stage || ''),
                    progress: Number(data.progress || 0),
                    message: String(data.message || ''),
                    videoUrl: typeof data.video_url === 'string' ? data.video_url : undefined,
                });
            }
        };

        ws.onerror = (error) => {
            console.error('[WS] Error:', error);
        };

        ws.onclose = () => {
            console.log('[WS] Disconnected');
        };

        wsRef.current = ws;
        return ws;
    }, []);

    useEffect(() => {
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    // Load series from localStorage
    useEffect(() => {
        const stored = localStorage.getItem(SERIES_STORAGE_KEY);
        const parsed = safeJsonParse<Series[]>(stored, []);
        if (parsed.length > 0) {
            setSeries(parsed);
            setCurrentSeries(parsed[0]);
        }
    }, []);

    const saveSeries = (newSeries: Series[]) => {
        localStorage.setItem(SERIES_STORAGE_KEY, JSON.stringify(newSeries));
        setSeries(newSeries);
    };

    // Load prompts from localStorage
    useEffect(() => {
        const storedPrompts = localStorage.getItem(PROMPTS_STORAGE_KEY);
        const parsed = safeJsonParse<{
            episodes?: Array<{ number: number; title: string; synopsis: string; prompt: string }>;
            title?: string;
            logline?: string;
            idea?: string;
        } | null>(storedPrompts, null);
        if (parsed) {
            if (parsed.episodes) setGeneratedEpisodes(parsed.episodes);
            if (parsed.title) setSeriesTitle(parsed.title);
            if (parsed.logline) setSeriesLogline(parsed.logline);
            if (parsed.idea) setStoryIdea(parsed.idea);
        }
    }, []);

    useEffect(() => {
        if (generatedEpisodes.length > 0) {
            localStorage.setItem(PROMPTS_STORAGE_KEY, JSON.stringify({
                episodes: generatedEpisodes,
                title: seriesTitle,
                logline: seriesLogline,
                idea: storyIdea
            }));
        }
    }, [generatedEpisodes, seriesTitle, seriesLogline, storyIdea]);

    // Load project from ?project= query parameter
    useEffect(() => {
        const projectId = searchParams.get('project');
        if (!projectId) return;

        const loadProject = async () => {
            try {
                // Clear localStorage drafts to avoid conflicts
                localStorage.removeItem(PROMPTS_STORAGE_KEY);
                localStorage.removeItem(SERIES_STORAGE_KEY);
                setGeneratedEpisodes([]);
                setSeriesTitle('');
                setSeriesLogline('');
                setStoryIdea('');

                const res = await fetch(`${API_V1_BASE_URL}/projects/${projectId}`);
                if (!res.ok) return;
                const data = await res.json();
                setLoadedProject(data);

                // Auto-select mode based on total_episodes
                const totalEp = data.total_episodes || 1;
                if (totalEp > 1) {
                    setMode('story');
                    if (data.logline) setStoryIdea(data.logline);
                    if (data.genre) setStoryGenre(data.genre);
                    setStoryEpisodesCount(Math.min(totalEp, 10));
                } else {
                    setMode('single');
                    if (data.logline) setPrompt(data.logline);
                }

                // Auto-set duration from project's episode_duration_sec
                const epDur = data.episode_duration_sec;
                if (epDur) {
                    // Find closest available duration for current model
                    const findClosest = (durations: number[]) =>
                        durations.reduce((prev, curr) =>
                            Math.abs(curr - epDur) < Math.abs(prev - epDur) ? curr : prev
                        );

                    if (totalEp > 1) {
                        // Story mode — pick best model by duration match
                        const minimaxDist = Math.abs(6 - epDur);
                        const veo31Dist = Math.abs(8 - epDur);
                        if (veo31Dist < minimaxDist) {
                            setStoryModel('veo31');
                        } else {
                            setStoryModel('minimax');
                        }
                    } else {
                        // Single mode — set duration for selected model
                        const closest = findClosest(MODEL_CONFIG[model].durations);
                        setDuration(closest);
                    }
                }
            } catch (e) {
                console.error('Failed to load project:', e);
            }
        };
        loadProject();
    }, [searchParams]);

    const generateEpisode = async (
        episodePrompt: string,
        customRefUrl?: string | null,
        subjectRefUrl?: string | null,
        referenceImages?: string[] | null,
        useModel?: ModelType,
        customDuration?: number,
        customAspectRatio?: string,
        sessionId?: string
    ): Promise<GenerationResult> => {
        const selectedModel = useModel || model;
        const modelConfig = MODEL_CONFIG[selectedModel];
        const finalDuration = customDuration || modelConfig.defaultDuration;
        const finalAspectRatio = customAspectRatio || (modelConfig.aspectRatios.includes(aspectRatio) ? aspectRatio : modelConfig.aspectRatios[0]);

        const response = await fetch(`${API_V1_BASE_URL}/episodes/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: episodePrompt.trim(),
                duration: finalDuration,
                aspect_ratio: finalAspectRatio,
                model: selectedModel,
                reference_image_url: customRefUrl !== undefined ? customRefUrl : null,
                subject_reference_url: subjectRefUrl !== undefined ? subjectRefUrl : null,
                reference_images: referenceImages !== undefined ? referenceImages : null,
                session_id: sessionId || null,
            }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = typeof data?.detail === 'string'
                ? data.detail
                : typeof data?.error === 'string'
                    ? data.error
                    : `Generation request failed (${response.status})`;
            throw new Error(detail);
        }
        return data as GenerationResult;
    };

    const handleGenerate = async () => {
        if (!prompt.trim()) {
            setError(t('generate.errorEmptyPrompt'));
            return;
        }

        setError(null);
        setResult(null);
        setIsGenerating(true);
        setGenerationProgress(null);
        setSentToReview(false);

        const sessionId = generateSessionId();
        sessionIdRef.current = sessionId;
        connectWebSocket(sessionId);

        try {
            const data = await generateEpisode(prompt, referenceImageUrl, null, null, undefined, undefined, undefined, sessionId);
            setResult(data);

            if (data.success && data.video_url) {
                addEpisodeToCurrentSeries(prompt, data.video_url, data.duration || duration);
            } else {
                setError(data.error || 'Generation failed');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to generate video');
        } finally {
            setIsGenerating(false);
            setGenerationProgress(null);
            if (wsRef.current) {
                wsRef.current.close();
            }
        }
    };

    const handleBatchGenerate = async () => {
        const validPrompts = batchPrompts.filter(p => p.trim());
        if (validPrompts.length === 0) {
            setError(t('generate.errorEmptyBatch'));
            return;
        }

        setIsGenerating(true);
        setError(null);
        setResult(null);
        setGenerationProgress(null);

        const batchGeneratedEpisodes: Episode[] = [];

        for (let i = 0; i < validPrompts.length; i++) {
            setBatchProgress({ current: i + 1, total: validPrompts.length });

            const sessionId = generateSessionId();
            sessionIdRef.current = sessionId;
            connectWebSocket(sessionId);

            try {
                const data = await generateEpisode(validPrompts[i], null, null, null, undefined, undefined, undefined, sessionId);

                if (data.success && data.video_url) {
                    batchGeneratedEpisodes.push({
                        id: `${Date.now()}-${i}`,
                        prompt: validPrompts[i],
                        video_url: data.video_url,
                        duration: data.duration || duration,
                        created_at: new Date().toISOString(),
                    });
                }
            } catch (err) {
                console.error(`Failed to generate episode ${i + 1}:`, err);
            }

            if (wsRef.current) {
                wsRef.current.close();
            }
        }

        if (batchGeneratedEpisodes.length > 0) {
            addMultipleEpisodesToSeries(batchGeneratedEpisodes);
        }

        setIsGenerating(false);
        setBatchProgress(null);
        setGenerationProgress(null);
        setBatchPrompts(['']);
    };

    const addMultipleEpisodesToSeries = (episodes: Episode[]) => {
        if (currentSeries) {
            const updated = series.map(s =>
                s.id === currentSeries.id
                    ? { ...s, episodes: [...s.episodes, ...episodes] }
                    : s
            );
            saveSeries(updated);
            setCurrentSeries(updated.find(s => s.id === currentSeries.id) || null);
        } else {
            const newSeries: Series = {
                id: Date.now().toString(),
                name: `Series ${series.length + 1}`,
                episodes: episodes,
                created_at: new Date().toISOString(),
            };
            saveSeries([...series, newSeries]);
            setCurrentSeries(newSeries);
        }
    };

    const addEpisodeToCurrentSeries = (episodePrompt: string, videoUrl: string, dur: number) => {
        const episode: Episode = {
            id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            prompt: episodePrompt,
            video_url: videoUrl,
            duration: dur,
            created_at: new Date().toISOString(),
        };

        if (currentSeries) {
            const updated = series.map(s =>
                s.id === currentSeries.id
                    ? { ...s, episodes: [...s.episodes, episode] }
                    : s
            );
            saveSeries(updated);
            setCurrentSeries(updated.find(s => s.id === currentSeries.id) || null);
        } else {
            const newSeries: Series = {
                id: Date.now().toString(),
                name: `Series ${series.length + 1}`,
                episodes: [episode],
                created_at: new Date().toISOString(),
            };
            saveSeries([...series, newSeries]);
            setCurrentSeries(newSeries);
        }
    };

    const createNewSeries = () => {
        const newSeries: Series = {
            id: Date.now().toString(),
            name: `Series ${series.length + 1}`,
            episodes: [],
            created_at: new Date().toISOString(),
        };
        saveSeries([...series, newSeries]);
        setCurrentSeries(newSeries);
    };

    const deleteEpisode = (episodeId: string) => {
        if (!currentSeries) return;
        const updated = series.map(s =>
            s.id === currentSeries.id
                ? { ...s, episodes: s.episodes.filter(e => e.id !== episodeId) }
                : s
        );
        saveSeries(updated);
        setCurrentSeries(updated.find(s => s.id === currentSeries.id) || null);
    };

    const moveEpisode = (index: number, direction: 'up' | 'down') => {
        if (!currentSeries) return;
        const episodes = [...currentSeries.episodes];
        const newIndex = direction === 'up' ? index - 1 : index + 1;
        if (newIndex < 0 || newIndex >= episodes.length) return;

        [episodes[index], episodes[newIndex]] = [episodes[newIndex], episodes[index]];

        const updated = series.map(s =>
            s.id === currentSeries.id ? { ...s, episodes } : s
        );
        saveSeries(updated);
        setCurrentSeries(updated.find(s => s.id === currentSeries.id) || null);
    };

    const handleMergeSeries = async () => {
        if (!currentSeries || currentSeries.episodes.length < 2) {
            setError(t('generate.errorMerge'));
            return;
        }

        setIsMerging(true);
        setError(null);

        try {
            const response = await fetch(`${API_V1_BASE_URL}/episodes/merge`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_urls: currentSeries.episodes.map(e => e.video_url),
                    transition: 'crossfade',
                    transition_duration: 0.5,
                }),
            });

            const data = await response.json();
            console.log('Merge response:', data);

            if (data.success && data.merged_video_url) {
                try {
                    const videoResponse = await fetch(data.merged_video_url);
                    const blob = await videoResponse.blob();
                    const blobUrl = URL.createObjectURL(blob);

                    const link = document.createElement('a');
                    link.href = blobUrl;
                    link.download = `${currentSeries.name.replace(/[^a-zA-Z0-9]/g, '_')}_merged.mp4`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);

                    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
                } catch (downloadErr) {
                    window.open(data.merged_video_url, '_blank');
                }
            } else {
                setError(data.error || 'Merge failed');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to merge videos');
        } finally {
            setIsMerging(false);
        }
    };

    const addBatchPrompt = () => {
        setBatchPrompts([...batchPrompts, '']);
    };

    const removeBatchPrompt = (index: number) => {
        setBatchPrompts(batchPrompts.filter((_, i) => i !== index));
    };

    const updateBatchPrompt = (index: number, value: string) => {
        const updated = [...batchPrompts];
        updated[index] = value;
        setBatchPrompts(updated);
    };

    // ==================== SEND TO REVIEW ====================

    const handleSendToReview = async () => {
        if (!result?.video_url) return;

        setSendingToReview(true);
        try {
            let title = prompt.substring(0, 100);
            let description = '';
            let tags: string[] = [];
            let project_id: number | undefined;

            if (loadedProject) {
                title = loadedProject.seo_title || loadedProject.title || title;
                description = loadedProject.seo_description || loadedProject.logline || '';
                project_id = loadedProject.id;
                if (loadedProject.seo_tags_json) {
                    tags = safeStringArray(loadedProject.seo_tags_json);
                }
            }

            const res = await fetch(`${API_V1_BASE_URL}/review/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_url: result.video_url,
                    title,
                    description,
                    tags,
                    project_id: project_id || null,
                }),
            });

            if (res.ok) {
                setSentToReview(true);
            } else {
                const data = await res.json();
                setError(data.detail || 'Failed to send to review');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send to review');
        } finally {
            setSendingToReview(false);
        }
    };

    // ==================== STORY MODE FUNCTIONS ====================

    const generateStoryPrompts = async () => {
        if (!storyIdea.trim() || storyIdea.length < 10) {
            setError(t('generate.errorStoryIdea'));
            return;
        }

        setIsGeneratingStory(true);
        setError(null);
        setGeneratedEpisodes([]);
        setCharacterImageUrl(null);
        setCharacterName('');
        setCharacterDescription('');

        const modelConfig = MODEL_CONFIG[storyModel];

        try {
            const response = await fetch(`${API_V1_BASE_URL}/episodes/generate-story-consistent`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    idea: storyIdea.trim(),
                    genre: storyGenre,
                    episodes_count: storyEpisodesCount,
                    duration: modelConfig.defaultDuration,
                    aspect_ratio: modelConfig.aspectRatios[0],
                    model: storyModel
                }),
            });

            const data = await response.json();

            if (data.success && data.episodes) {
                setSeriesTitle(data.series_title || 'Untitled Series');
                setSeriesLogline(data.logline || '');
                setGeneratedEpisodes(data.episodes);

                if (data.character_image_url) {
                    setCharacterImageUrl(data.character_image_url);
                    setCharacterName(data.character_name || 'Main Character');
                    setCharacterDescription(data.character_description || '');
                    console.log('[Story Mode] Character image ready:', data.character_image_url);
                }
            } else {
                setError(data.error || 'Failed to generate story');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to generate story prompts');
        } finally {
            setIsGeneratingStory(false);
        }
    };

    const updateGeneratedPrompt = (index: number, newPrompt: string) => {
        const updated = [...generatedEpisodes];
        updated[index] = { ...updated[index], prompt: newPrompt };
        setGeneratedEpisodes(updated);
    };

    const handleStoryGenerate = async () => {
        if (generatedEpisodes.length === 0) {
            setError(t('generate.errorNoEpisodes'));
            return;
        }

        setIsGenerating(true);
        setError(null);
        setGenerationProgress(null);

        const generatedVideos: Episode[] = [];
        const modelConfig = MODEL_CONFIG[storyModel];

        const effectiveCharacterImage = referenceImageUrl || characterImageUrl;

        const subjectReference = (isConsistencyEnabled && storyModel === 'minimax') ? effectiveCharacterImage : null;
        const referenceImagesArray = (isConsistencyEnabled && storyModel === 'veo31')
            ? (veoReferenceImages.length > 0 ? veoReferenceImages : (effectiveCharacterImage ? [effectiveCharacterImage] : null))
            : null;

        console.log(`[Story Mode ${storyModel}] Starting generation with consistency=${isConsistencyEnabled}`);
        console.log(`[Story Mode ${storyModel}] Reference: uploaded=${referenceImageUrl ? 'yes' : 'no'}, autoGenerated=${characterImageUrl ? 'yes' : 'no'}, veoImages=${veoReferenceImages.length}`);
        console.log(`[Story Mode ${storyModel}] Model config: duration=${modelConfig.defaultDuration}, aspectRatio=${modelConfig.aspectRatios[0]}`);

        for (let i = 0; i < generatedEpisodes.length; i++) {
            setBatchProgress({ current: i + 1, total: generatedEpisodes.length });

            const sessionId = generateSessionId();
            sessionIdRef.current = sessionId;
            connectWebSocket(sessionId);

            try {
                console.log(`[Story Mode ${storyModel}] Generating episode ${i + 1}/${generatedEpisodes.length}: ${generatedEpisodes[i].prompt.slice(0, 50)}...`);

                let data = null;
                for (let attempt = 1; attempt <= 2; attempt++) {
                    data = await generateEpisode(
                        generatedEpisodes[i].prompt,
                        null,
                        subjectReference,
                        referenceImagesArray,
                        storyModel,
                        modelConfig.defaultDuration,
                        modelConfig.aspectRatios[0],
                        sessionId
                    );
                    console.log(`[Story Mode ${storyModel}] Episode ${i + 1} attempt ${attempt} response:`, { success: data.success, hasVideoUrl: !!data.video_url, error: data.error });

                    if (data.success && data.video_url) {
                        break;
                    } else if (attempt < 2) {
                        console.log(`[Story Mode ${storyModel}] Episode ${i + 1} failed, retrying in 2 seconds...`);
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }
                }

                if (data?.success && data?.video_url) {
                    generatedVideos.push({
                        id: `${Date.now()}-${i}`,
                        prompt: generatedEpisodes[i].prompt,
                        video_url: data.video_url,
                        duration: data.duration || modelConfig.defaultDuration,
                        created_at: new Date().toISOString(),
                    });
                    console.log(`[Story Mode ${storyModel}] Episode ${i + 1} added successfully`);
                } else {
                    console.warn(`[Story Mode ${storyModel}] Episode ${i + 1} skipped after 2 attempts - no video_url, error: ${data?.error}`);
                }
            } catch (err) {
                console.error(`Failed to generate episode ${i + 1}:`, err);
            }

            if (wsRef.current) {
                wsRef.current.close();
            }
        }

        if (generatedVideos.length > 0) {
            const newSeries: Series = {
                id: Date.now().toString(),
                name: seriesTitle || `Story Series ${series.length + 1}`,
                episodes: generatedVideos,
                created_at: new Date().toISOString(),
            };
            saveSeries([...series, newSeries]);
            setCurrentSeries(newSeries);
        }

        setIsGenerating(false);
        setBatchProgress(null);
        setGenerationProgress(null);
    };

    return (
        <div className="min-h-screen bg-[var(--background)]">
            <div className="container mx-auto p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <Link href="/" className="text-purple-300 hover:text-purple-100 transition-colors">
                        {t('generate.back')}
                    </Link>
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 text-transparent bg-clip-text">
                        {t('generate.title')}
                    </h1>
                    <LanguageSwitcher />
                </div>

                {/* Loaded Project Banner */}
                {loadedProject && (
                    <div className="bg-gradient-to-r from-green-500/10 to-purple-500/10 border border-green-500/30 rounded-xl p-4 mb-4">
                        <div className="flex items-start justify-between">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                    <Sparkles className="w-5 h-5 text-green-400" />
                                    <h3 className="font-medium text-green-400">{t('generate.projectLoaded')}</h3>
                                    <span className="text-xs bg-gray-700/50 px-2 py-0.5 rounded">ID: {loadedProject.id}</span>
                                </div>
                                <p className="text-white font-medium mb-1">{loadedProject.title}</p>
                                {loadedProject.logline && (
                                    <p className="text-gray-400 text-sm mb-2">{loadedProject.logline}</p>
                                )}
                                {loadedProject.genre && (
                                    <span className="text-xs text-gray-500">{t('generate.projectGenre', { genre: loadedProject.genre })}</span>
                                )}
                                {loadedProject.seo_tags_json && (
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        {safeStringArray(loadedProject.seo_tags_json).slice(0, 10).map((tag: string, i: number) => (
                                            <span key={i} className="text-[10px] bg-green-500/15 text-green-400 px-1.5 py-0.5 rounded">#{tag}</span>
                                        ))}
                                    </div>
                                )}
                                <p className="text-yellow-400 text-xs mt-2">{t('generate.projectReviewHint')}</p>
                            </div>
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left Column - Generator */}
                    <div className="lg:col-span-2 space-y-4">
                        {/* Mode Toggle */}
                        <div className="flex gap-2 bg-white/5 p-1 rounded-xl w-fit">
                            <button
                                onClick={() => setMode('single')}
                                className={`px-4 py-2 rounded-lg font-medium transition-all ${mode === 'single'
                                    ? 'bg-purple-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                {t('generate.singleEpisode')}
                            </button>
                            <button
                                onClick={() => setMode('batch')}
                                className={`px-4 py-2 rounded-lg font-medium transition-all ${mode === 'batch'
                                    ? 'bg-purple-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                {t('generate.batchEpisodes')}
                            </button>
                            <button
                                onClick={() => setMode('story')}
                                className={`px-4 py-2 rounded-lg font-medium transition-all ${mode === 'story'
                                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                {t('generate.storyMode')}
                            </button>
                        </div>

                        {/* Reference Image */}
                        {mode !== 'batch' && (
                        <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                                <Camera className="w-4 h-4" /> {mode === 'story' && storyModel === 'veo31' ? t('generate.referenceImages') : t('generate.referenceImage')}
                                {mode === 'story' ? (
                                    storyModel === 'veo31' ? (
                                        <span className="text-purple-400 text-sm">{t('generate.upTo3R2V')}</span>
                                    ) : (
                                        <span className="text-purple-400 text-sm">{t('generate.characterForAll')}</span>
                                    )
                                ) : (
                                    <span className="text-gray-500 text-sm">{t('generate.optional')}</span>
                                )}
                            </h3>
                            {mode === 'story' && storyModel === 'veo31' ? (
                                <div className="space-y-3">
                                    <div className="grid grid-cols-3 gap-3">
                                        {[0, 1, 2].map((index) => (
                                            <div key={index} className="relative">
                                                {veoReferenceImages[index] ? (
                                                    <div className="relative group">
                                                        <img
                                                            src={veoReferenceImages[index]}
                                                            alt={`Reference ${index + 1}`}
                                                            className="w-full h-24 object-cover rounded-lg border border-white/20"
                                                        />
                                                        <button
                                                            onClick={() => {
                                                                const newImages = [...veoReferenceImages];
                                                                newImages.splice(index, 1);
                                                                setVeoReferenceImages(newImages);
                                                            }}
                                                            className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                                                        >
                                                            ✕
                                                        </button>
                                                        <span className="absolute bottom-1 left-1 bg-black/60 text-white text-xs px-1.5 py-0.5 rounded">
                                                            {index + 1}
                                                        </span>
                                                    </div>
                                                ) : veoReferenceImages.length === index ? (
                                                    <ImageUpload
                                                        apiBaseUrl={API_BASE_URL}
                                                        onImageUploaded={(url) => {
                                                            setVeoReferenceImages([...veoReferenceImages, url]);
                                                        }}
                                                        onImageRemoved={() => {}}
                                                        compact={true}
                                                    />
                                                ) : (
                                                    <div className="w-full h-24 bg-black/20 rounded-lg border border-dashed border-white/10 flex items-center justify-center text-gray-600 text-xs">
                                                        {index + 1}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                    <p className="text-gray-500 text-xs">
                                        {t('generate.r2vHint')}
                                    </p>
                                </div>
                            ) : (
                                <>
                                    <ImageUpload
                                        apiBaseUrl={API_BASE_URL}
                                        onImageUploaded={(url) => setReferenceImageUrl(url)}
                                        onImageRemoved={() => setReferenceImageUrl(null)}
                                    />
                                    {mode === 'story' && (
                                        <p className="text-gray-500 text-xs mt-2">
                                            {t('generate.characterUploadHint')}
                                            {!referenceImageUrl && t('generate.characterAutoHint')}
                                        </p>
                                    )}
                                </>
                            )}
                        </div>
                        )}

                        {/* Single Mode */}
                        {mode === 'single' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><PenLine className="w-4 h-4" /> {t('generate.prompt')}</h3>
                                <textarea
                                    value={prompt}
                                    onChange={(e) => setPrompt(e.target.value)}
                                    placeholder={t('generate.promptPlaceholder')}
                                    className="w-full h-32 bg-black/30 border border-white/10 rounded-lg p-3 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-purple-500"
                                />
                            </div>
                        )}

                        {/* Batch Mode */}
                        {mode === 'batch' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <div className="flex justify-between items-center mb-3">
                                    <h3 className="text-white font-medium flex items-center gap-2"><PenLine className="w-4 h-4" /> {t('generate.episodePrompts')}</h3>
                                    <button
                                        onClick={addBatchPrompt}
                                        className="text-purple-400 hover:text-purple-300 text-sm"
                                    >
                                        {t('generate.addEpisode')}
                                    </button>
                                </div>
                                <div className="space-y-3">
                                    {batchPrompts.map((p, i) => (
                                        <div key={i} className="flex gap-2">
                                            <span className="text-gray-500 mt-2 w-6">{i + 1}.</span>
                                            <textarea
                                                value={p}
                                                onChange={(e) => updateBatchPrompt(i, e.target.value)}
                                                placeholder={t('generate.episodePlaceholder', { count: i + 1 })}
                                                className="flex-1 h-20 bg-black/30 border border-white/10 rounded-lg p-3 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-purple-500"
                                            />
                                            {batchPrompts.length > 1 && (
                                                <button
                                                    onClick={() => removeBatchPrompt(i)}
                                                    className="text-red-400 hover:text-red-300"
                                                >
                                                    ✕
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>

                            </div>
                        )}

                        {/* Story Mode */}
                        {mode === 'story' && (
                            <div className="space-y-4">
                                {/* Step 1: Idea Input */}
                                <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                    <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                                        <Sparkles className="w-4 h-4" /> {t('generate.storyIdea')}
                                    </h3>
                                    <textarea
                                        value={storyIdea}
                                        onChange={(e) => setStoryIdea(e.target.value)}
                                        placeholder={t('generate.storyIdeaPlaceholder')}
                                        className="w-full h-24 bg-black/30 border border-white/10 rounded-lg p-3 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-purple-500"
                                    />

                                    <div className="grid grid-cols-3 gap-4 mt-4">
                                        <div>
                                            <label className="text-gray-400 text-sm mb-1 block">{t('generate.genre')}</label>
                                            <select
                                                value={storyGenre}
                                                onChange={(e) => setStoryGenre(e.target.value)}
                                                className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                            >
                                                <option value="drama">{t('generate.genreDrama')}</option>
                                                <option value="comedy">{t('generate.genreComedy')}</option>
                                                <option value="thriller">{t('generate.genreThriller')}</option>
                                                <option value="fantasy">{t('generate.genreFantasy')}</option>
                                                <option value="romance">{t('generate.genreRomance')}</option>
                                                <option value="action">{t('generate.genreAction')}</option>
                                                <option value="horror">{t('generate.genreHorror')}</option>
                                                <option value="scifi">{t('generate.genreSciFi')}</option>
                                                <option value="mystery">{t('generate.genreMystery')}</option>
                                                <option value="melodrama">{t('generate.genreMelodrama')}</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="text-gray-400 text-sm mb-1 block">{t('generate.aiModel')}</label>
                                            <select
                                                value={storyModel}
                                                onChange={(e) => setStoryModel(e.target.value as 'minimax' | 'veo31')}
                                                className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                            >
                                                <option value="minimax">MiniMax (6 сек, 9:16)</option>
                                                <option value="veo31">Veo 3.1 (8 сек, 16:9)</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="text-gray-400 text-sm mb-1 block">{t('generate.episodes', { count: storyEpisodesCount })}</label>
                                            <input
                                                type="range"
                                                min={1}
                                                max={10}
                                                value={storyEpisodesCount}
                                                onChange={(e) => setStoryEpisodesCount(parseInt(e.target.value))}
                                                className="w-full accent-purple-500 mt-2"
                                            />
                                        </div>
                                    </div>

                                    <button
                                        onClick={generateStoryPrompts}
                                        disabled={isGeneratingStory || !storyIdea.trim()}
                                        className={`mt-4 w-full py-3 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${isGeneratingStory || !storyIdea.trim()
                                            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                            : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:opacity-90'
                                            }`}
                                    >
                                        {isGeneratingStory ? (
                                            <>
                                                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                                {t('generate.generatingPrompts')}
                                            </>
                                        ) : (
                                            <>
                                                <Sparkles className="w-4 h-4" /> {t('generate.generateEpisodePrompts')}
                                            </>
                                        )}
                                    </button>
                                </div>

                                {/* Step 2: Preview & Edit Generated Episodes */}
                                {generatedEpisodes.length > 0 && (
                                    <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                        <div className="flex justify-between items-center mb-3">
                                            <h3 className="text-white font-medium flex items-center gap-2">
                                                <BookOpen className="w-4 h-4" /> {seriesTitle}
                                            </h3>
                                            <span className="text-gray-500 text-sm">{t('generate.episodesCount', { count: generatedEpisodes.length })}</span>
                                        </div>
                                        {seriesLogline && (
                                            <p className="text-gray-400 text-sm mb-4 italic">{seriesLogline}</p>
                                        )}

                                        <div className="space-y-3 max-h-96 overflow-y-auto">
                                            {generatedEpisodes.map((ep, i) => (
                                                <div key={i} className="bg-black/30 rounded-lg p-3">
                                                    <div className="flex justify-between items-center mb-2">
                                                        <span className="text-purple-400 font-medium text-sm">
                                                            {t('generate.episodeNumber', { count: ep.number })}{ep.title}
                                                        </span>
                                                    </div>
                                                    <p className="text-gray-500 text-xs mb-2">{ep.synopsis}</p>
                                                    <textarea
                                                        value={ep.prompt}
                                                        onChange={(e) => updateGeneratedPrompt(i, e.target.value)}
                                                        className="w-full h-20 bg-black/50 border border-white/10 rounded-lg p-2 text-white text-sm resize-none focus:outline-none focus:border-purple-500"
                                                    />
                                                </div>
                                            ))}
                                        </div>


                                    </div>
                                )}

                                {/* Character Preview */}
                                {characterImageUrl && !referenceImageUrl && (
                                    <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                        <div className="flex items-center justify-between mb-3">
                                            <h3 className="text-white font-medium flex items-center gap-2">
                                                <User className="w-4 h-4" /> {t('generate.mainCharacter')}
                                            </h3>
                                            <label className="flex items-center gap-2 text-sm cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={isConsistencyEnabled}
                                                    onChange={(e) => setIsConsistencyEnabled(e.target.checked)}
                                                    className="w-4 h-4 rounded bg-black/30 border-white/20 text-purple-500 focus:ring-purple-500"
                                                />
                                                <span className="text-gray-400">{t('generate.characterConsistency')}</span>
                                            </label>
                                        </div>
                                        <div className="flex gap-4">
                                            <img
                                                src={characterImageUrl}
                                                alt={characterName}
                                                className="w-24 h-32 object-cover rounded-lg border border-white/20"
                                            />
                                            <div className="flex-1">
                                                <p className="text-purple-400 font-medium">{characterName}</p>
                                                <p className="text-gray-400 text-sm mt-1 line-clamp-3">
                                                    {characterDescription || t('generate.consistencyDefault')}
                                                </p>
                                                {isConsistencyEnabled ? (
                                                    <p className="text-green-400 text-xs mt-2 flex items-center gap-1">
                                                        <Link2 className="w-3 h-3" /> {MODEL_CONFIG[storyModel].name}: {MODEL_CONFIG[storyModel].consistencyNote}
                                                    </p>
                                                ) : (
                                                    <p className="text-yellow-400 text-xs mt-2 flex items-center gap-1">
                                                        <AlertTriangle className="w-3 h-3" /> {t('generate.consistencyDisabled')}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Settings */}
                        {mode !== 'story' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><Settings className="w-4 h-4" /> {t('generate.settings')}</h3>
                                <div className="grid grid-cols-3 gap-4">
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">{t('generate.duration')}</label>
                                        <select
                                            value={duration}
                                            onChange={(e) => setDuration(parseInt(e.target.value))}
                                            className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                        >
                                            <option value={4} className="bg-gray-800 text-white">{t('generate.seconds', { count: 4 })}</option>
                                            <option value={6} className="bg-gray-800 text-white">{t('generate.seconds', { count: 6 })}</option>
                                            <option value={8} className="bg-gray-800 text-white">{t('generate.seconds', { count: 8 })}</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">{t('generate.aspectRatio')}</label>
                                        <select
                                            value={aspectRatio}
                                            onChange={(e) => setAspectRatio(e.target.value)}
                                            className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                        >
                                            <option value="9:16" className="bg-gray-800 text-white">{t('generate.vertical')}</option>
                                            <option value="16:9" className="bg-gray-800 text-white">{t('generate.horizontal')}</option>
                                            {model === 'kling' && (
                                                <option value="1:1" className="bg-gray-800 text-white">{t('generate.square')}</option>
                                            )}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">{t('generate.aiModel')}</label>
                                        <select
                                            value={model}
                                            onChange={(e) => setModel(e.target.value as 'veo3' | 'kling')}
                                            className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                        >
                                            <option value="veo3" className="bg-gray-800 text-white">Veo 3 (Google)</option>
                                            <option value="kling" className="bg-gray-800 text-white">Kling AI (Kuaishou)</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Generate Button */}
                        <button
                            onClick={mode === 'single' ? handleGenerate : mode === 'batch' ? handleBatchGenerate : handleStoryGenerate}
                            disabled={
                                isGenerating ||
                                (mode === 'single' && !prompt.trim()) ||
                                (mode === 'batch' && batchPrompts.every(p => !p.trim())) ||
                                (mode === 'story' && generatedEpisodes.length === 0)
                            }
                            className={`w-full py-4 rounded-xl font-bold text-lg transition-all ${isGenerating ||
                                (mode === 'single' && !prompt.trim()) ||
                                (mode === 'batch' && batchPrompts.every(p => !p.trim())) ||
                                (mode === 'story' && generatedEpisodes.length === 0)
                                ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:opacity-90'
                                }`}
                        >
                            {isGenerating ? (
                                <span className="flex items-center justify-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    {batchProgress
                                        ? t('generate.generatingEpisode', { current: batchProgress.current, total: batchProgress.total })
                                        : t('generate.generating')
                                    }
                                </span>
                            ) : (
                                <span className="flex items-center justify-center gap-2">
                                    <Play className="w-5 h-5" />
                                    {mode === 'single'
                                        ? t('generate.generateEpisode')
                                        : mode === 'batch'
                                            ? t('generate.generateNEpisodes', { count: batchPrompts.filter(p => p.trim()).length })
                                            : t('generate.generateStoryEpisodes', { count: generatedEpisodes.length })
                                    }
                                </span>
                            )}
                        </button>

                        {/* Progress Indicator */}
                        {isGenerating && generationProgress && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-white font-medium text-sm">
                                        {generationProgress.message}
                                    </span>
                                    <span className="text-purple-400 text-sm">
                                        {generationProgress.progress}%
                                    </span>
                                </div>
                                <div className="w-full bg-gray-700 rounded-full h-2">
                                    <div
                                        className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full transition-all duration-300"
                                        style={{ width: `${generationProgress.progress}%` }}
                                    />
                                </div>
                                <p className="text-gray-500 text-xs mt-2 capitalize">
                                    {t('generate.stage', { stage: generationProgress.stage })}
                                </p>
                            </div>
                        )}

                        {error && (
                            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-red-300 text-sm">
                                <AlertTriangle className="w-4 h-4 inline mr-1" /> {error}
                            </div>
                        )}

                        {/* Last Result Preview */}
                        {result?.success && result.video_url && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><Play className="w-4 h-4" /> {t('generate.latestGeneration')}</h3>
                                <video
                                    src={result.video_url}
                                    controls
                                    autoPlay
                                    loop
                                    muted
                                    className="w-full max-w-sm rounded-lg mx-auto"
                                />
                                <div className="mt-3 flex justify-center">
                                    {sentToReview ? (
                                        <Link
                                            href="/review"
                                            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition-colors"
                                        >
                                            <CheckCircle className="w-4 h-4" />
                                            {t('generate.goToReview')}
                                        </Link>
                                    ) : (
                                        <button
                                            onClick={handleSendToReview}
                                            disabled={sendingToReview}
                                            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                                                sendingToReview
                                                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                                                    : 'bg-blue-600 hover:bg-blue-500 text-white'
                                            }`}
                                        >
                                            {sendingToReview ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    {t('generate.sendingToReview')}
                                                </>
                                            ) : (
                                                <>
                                                    <Send className="w-4 h-4" />
                                                    {t('generate.sendToReview')}
                                                </>
                                            )}
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Right Column - Series Panel */}
                    <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10 h-fit mt-16">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-white font-medium flex items-center gap-2"><Film className="w-4 h-4" /> {t('generate.series')}</h3>
                            <button
                                onClick={createNewSeries}
                                className="text-purple-400 hover:text-purple-300 text-sm"
                            >
                                {t('generate.newSeries')}
                            </button>
                        </div>

                        {/* Series Selector */}
                        {series.length > 0 && (
                            <select
                                value={currentSeries?.id || ''}
                                onChange={(e) => setCurrentSeries(series.find(s => s.id === e.target.value) || null)}
                                className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white mb-4 focus:outline-none focus:border-purple-500 font-sans"
                            >
                                {series.map(s => (
                                    <option key={s.id} value={s.id} className="bg-gray-800 text-white">{s.name} ({s.episodes.length} ep)</option>
                                ))}
                            </select>
                        )}

                        {/* Episodes List */}
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                            {currentSeries?.episodes.map((ep, i) => (
                                <div key={ep.id} className="bg-black/30 rounded-lg p-2 flex items-center gap-2">
                                    <span className="text-gray-500 text-sm w-5">{i + 1}</span>
                                    <video
                                        src={ep.video_url}
                                        className="w-12 h-16 object-cover rounded"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-white text-xs truncate">{ep.prompt.substring(0, 30)}...</p>
                                        <p className="text-gray-500 text-xs">{ep.duration}s</p>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <button
                                            onClick={() => moveEpisode(i, 'up')}
                                            disabled={i === 0}
                                            className="text-gray-500 hover:text-white disabled:opacity-30 text-xs"
                                        >
                                            ▲
                                        </button>
                                        <button
                                            onClick={() => moveEpisode(i, 'down')}
                                            disabled={i === currentSeries.episodes.length - 1}
                                            className="text-gray-500 hover:text-white disabled:opacity-30 text-xs"
                                        >
                                            ▼
                                        </button>
                                    </div>
                                    <button
                                        onClick={() => deleteEpisode(ep.id)}
                                        className="text-red-400 hover:text-red-300 text-xs"
                                    >
                                        ✕
                                    </button>
                                </div>
                            ))}
                        </div>

                        {(!currentSeries || currentSeries.episodes.length === 0) && (
                            <div className="text-center text-gray-500 py-8">
                                <Film className="w-8 h-8 mx-auto mb-2 text-gray-600" />
                                <p className="text-sm">{t('generate.generatedEpisodes')}</p>
                                <p className="text-sm">{t('generate.willAppearHere')}</p>
                            </div>
                        )}

                        {/* Merge Button */}
                        {currentSeries && currentSeries.episodes.length >= 2 && (
                            <button
                                onClick={handleMergeSeries}
                                disabled={isMerging}
                                className={`w-full mt-4 py-3 rounded-lg font-medium transition-all ${isMerging
                                    ? 'bg-gray-600 text-gray-400'
                                    : 'bg-green-600 hover:bg-green-500 text-white'
                                    }`}
                            >
                                {isMerging ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                        {t('generate.merging')}
                                    </span>
                                ) : (
                                    <span className="flex items-center justify-center gap-2"><Download className="w-4 h-4" /> {t('generate.mergeDownload')}</span>
                                )}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
