'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import ImageUpload from '@/components/ImageUpload';
import {
    Camera, PenLine, Settings, Link2, Film, AlertTriangle,
    Play, Trash2, ChevronUp, ChevronDown, Download, FolderOpen, Sparkles, BookOpen, User, Loader2
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace('http', 'ws');

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
        supportsI2V: false,
        supportsCharacterConsistency: false,
    },
    veo31: {
        name: 'Veo 3.1 (R2V)',
        durations: [4, 6, 8],
        defaultDuration: 8,  // R2V requires 8 sec
        aspectRatios: ['16:9'],  // R2V only supports 16:9
        supportsI2V: true,
        supportsCharacterConsistency: true,
        consistencyNote: 'R2V: 16:9, 8 сек',
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

// LocalStorage keys
const SERIES_STORAGE_KEY = 'ai_video_factory_series';
const PROMPTS_STORAGE_KEY = 'ai_video_factory_prompts';

export default function GenerateEpisodePage() {
    // Mode state
    const [mode, setMode] = useState<'single' | 'batch' | 'story'>('single');

    // Single mode state
    const [prompt, setPrompt] = useState('');
    const [duration, setDuration] = useState(4);
    const [aspectRatio, setAspectRatio] = useState('9:16');
    const [model, setModel] = useState<ModelType>('veo3');
    const [storyModel, setStoryModel] = useState<'minimax' | 'veo31'>('minimax');  // Model for Story Mode
    const [referenceImageUrl, setReferenceImageUrl] = useState<string | null>(null);

    // Reset aspectRatio and referenceImage when switching to Veo3 (doesn't support 1:1 and image-to-video)
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
    // Multiple reference images for Veo 3.1 R2V (up to 3)
    const [veoReferenceImages, setVeoReferenceImages] = useState<string[]>([]);

    // WebSocket progress state
    const [generationProgress, setGenerationProgress] = useState<GenerationProgress | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const sessionIdRef = useRef<string>('');

    // Generate unique session ID
    const generateSessionId = useCallback(() => {
        return `session_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    }, []);

    // Connect to WebSocket for progress updates
    const connectWebSocket = useCallback((sessionId: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.close();
        }

        const ws = new WebSocket(`${WS_BASE_URL}/api/v1/ws/session/${sessionId}`);

        ws.onopen = () => {
            console.log('[WS] Connected for progress updates');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'progress') {
                    setGenerationProgress({
                        stage: data.stage,
                        progress: data.progress,
                        message: data.message,
                        videoUrl: data.video_url,
                    });
                }
            } catch (e) {
                console.error('[WS] Parse error:', e);
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

    // Cleanup WebSocket on unmount
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
        if (stored) {
            const parsed = JSON.parse(stored);
            setSeries(parsed);
            if (parsed.length > 0) {
                setCurrentSeries(parsed[0]);
            }
        }
    }, []);

    // Save series to localStorage
    const saveSeries = (newSeries: Series[]) => {
        localStorage.setItem(SERIES_STORAGE_KEY, JSON.stringify(newSeries));
        setSeries(newSeries);
    };

    // Load prompts from localStorage
    useEffect(() => {
        const storedPrompts = localStorage.getItem(PROMPTS_STORAGE_KEY);
        if (storedPrompts) {
            const parsed = JSON.parse(storedPrompts);
            if (parsed.episodes) setGeneratedEpisodes(parsed.episodes);
            if (parsed.title) setSeriesTitle(parsed.title);
            if (parsed.logline) setSeriesLogline(parsed.logline);
            if (parsed.idea) setStoryIdea(parsed.idea);
        }
    }, []);

    // Save prompts to localStorage when they change
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

    // Generate single episode with optional custom reference and subject reference (for MiniMax character consistency)
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

        const response = await fetch(`${API_BASE_URL}/api/v1/episodes/generate`, {
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
        return await response.json();
    };

    // Handle single generate
    const handleGenerate = async () => {
        if (!prompt.trim()) {
            setError('Please enter a prompt');
            return;
        }

        setError(null);
        setResult(null);
        setIsGenerating(true);
        setGenerationProgress(null);

        // Setup WebSocket for progress
        const sessionId = generateSessionId();
        sessionIdRef.current = sessionId;
        connectWebSocket(sessionId);

        try {
            const data = await generateEpisode(prompt, referenceImageUrl, null, null, undefined, undefined, undefined, sessionId);
            setResult(data);

            if (data.success && data.video_url) {
                // Add to current series
                addEpisodeToCurrentSeries(prompt, data.video_url, data.duration || duration);
            } else {
                setError(data.error || 'Generation failed');
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to generate video');
        } finally {
            setIsGenerating(false);
            setGenerationProgress(null);
            // Close WebSocket after generation completes
            if (wsRef.current) {
                wsRef.current.close();
            }
        }
    };

    // Handle batch generate
    const handleBatchGenerate = async () => {
        const validPrompts = batchPrompts.filter(p => p.trim());
        if (validPrompts.length === 0) {
            setError('Please enter at least one prompt');
            return;
        }

        setIsGenerating(true);
        setError(null);
        setResult(null);
        setGenerationProgress(null);

        // Collect all generated episodes
        const batchGeneratedEpisodes: Episode[] = [];

        for (let i = 0; i < validPrompts.length; i++) {
            setBatchProgress({ current: i + 1, total: validPrompts.length });

            // Setup WebSocket for each episode
            const sessionId = generateSessionId();
            sessionIdRef.current = sessionId;
            connectWebSocket(sessionId);

            try {
                // Continuity disabled - generate each episode independently without reference images
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

            // Close WebSocket after each episode
            if (wsRef.current) {
                wsRef.current.close();
            }
        }

        // Add all episodes at once
        if (batchGeneratedEpisodes.length > 0) {
            addMultipleEpisodesToSeries(batchGeneratedEpisodes);
        }

        setIsGenerating(false);
        setBatchProgress(null);
        setGenerationProgress(null);
        setBatchPrompts(['']);
    };

    // Add multiple episodes to current series at once
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
            // Create new series with all episodes
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

    // Add single episode to current series
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
            // Create new series
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

    // Create new series
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

    // Delete episode from series
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

    // Reorder episodes
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

    // Merge series into one video
    const handleMergeSeries = async () => {
        if (!currentSeries || currentSeries.episodes.length < 2) {
            setError('Need at least 2 episodes to merge');
            return;
        }

        setIsMerging(true);
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/episodes/merge`, {
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
                // Download merged video using fetch + blob for cross-origin support
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

                    // Clean up blob URL
                    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
                } catch (downloadErr) {
                    // Fallback: open in new tab
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

    // Add batch prompt
    const addBatchPrompt = () => {
        setBatchPrompts([...batchPrompts, '']);
    };

    // Remove batch prompt
    const removeBatchPrompt = (index: number) => {
        setBatchPrompts(batchPrompts.filter((_, i) => i !== index));
    };

    // Update batch prompt
    const updateBatchPrompt = (index: number, value: string) => {
        const updated = [...batchPrompts];
        updated[index] = value;
        setBatchPrompts(updated);
    };

    // ==================== STORY MODE FUNCTIONS ====================

    // Generate story prompts from idea using GPT (with character consistency)
    const generateStoryPrompts = async () => {
        if (!storyIdea.trim() || storyIdea.length < 10) {
            setError('Please enter a story idea (at least 10 characters)');
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
            // Use new consistent story endpoint that also generates character image
            const response = await fetch(`${API_BASE_URL}/api/v1/episodes/generate-story-consistent`, {
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

                // Set character consistency data
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

    // Update generated episode prompt
    const updateGeneratedPrompt = (index: number, newPrompt: string) => {
        const updated = [...generatedEpisodes];
        updated[index] = { ...updated[index], prompt: newPrompt };
        setGeneratedEpisodes(updated);
    };

    // Generate videos from story prompts with character consistency
    const handleStoryGenerate = async () => {
        if (generatedEpisodes.length === 0) {
            setError('No episodes to generate. Generate prompts first.');
            return;
        }

        setIsGenerating(true);
        setError(null);
        setGenerationProgress(null);

        const generatedVideos: Episode[] = [];
        const modelConfig = MODEL_CONFIG[storyModel];

        // Use uploaded reference image if available, otherwise use auto-generated character image
        const effectiveCharacterImage = referenceImageUrl || characterImageUrl;

        // Character consistency setup based on selected model
        // - MiniMax S2V-01: uses subject_reference_url for identity consistency
        // - Veo 3.1 R2V: uses reference_images array (up to 3) for character consistency
        const subjectReference = (isConsistencyEnabled && storyModel === 'minimax') ? effectiveCharacterImage : null;
        // For Veo 3.1: use veoReferenceImages array if available, otherwise fallback to single effectiveCharacterImage
        const referenceImagesArray = (isConsistencyEnabled && storyModel === 'veo31')
            ? (veoReferenceImages.length > 0 ? veoReferenceImages : (effectiveCharacterImage ? [effectiveCharacterImage] : null))
            : null;

        console.log(`[Story Mode ${storyModel}] Starting generation with consistency=${isConsistencyEnabled}`);
        console.log(`[Story Mode ${storyModel}] Reference: uploaded=${referenceImageUrl ? 'yes' : 'no'}, autoGenerated=${characterImageUrl ? 'yes' : 'no'}, veoImages=${veoReferenceImages.length}`);
        console.log(`[Story Mode ${storyModel}] Model config: duration=${modelConfig.defaultDuration}, aspectRatio=${modelConfig.aspectRatios[0]}`);

        for (let i = 0; i < generatedEpisodes.length; i++) {
            setBatchProgress({ current: i + 1, total: generatedEpisodes.length });

            // Setup WebSocket for each episode
            const sessionId = generateSessionId();
            sessionIdRef.current = sessionId;
            connectWebSocket(sessionId);

            try {
                console.log(`[Story Mode ${storyModel}] Generating episode ${i + 1}/${generatedEpisodes.length}: ${generatedEpisodes[i].prompt.slice(0, 50)}...`);

                // Try up to 2 times (retry on moderation errors)
                let data = null;
                for (let attempt = 1; attempt <= 2; attempt++) {
                    // Generate with model-specific parameters
                    // subject_reference_url: MiniMax S2V-01 identity consistency
                    // reference_images: Veo 3.1 R2V character consistency
                    data = await generateEpisode(
                        generatedEpisodes[i].prompt,
                        null,  // reference_image_url (not used for MiniMax/Veo31)
                        subjectReference,  // subject_reference_url for MiniMax S2V-01
                        referenceImagesArray,  // reference_images for Veo 3.1 R2V
                        storyModel,
                        modelConfig.defaultDuration,
                        modelConfig.aspectRatios[0],
                        sessionId
                    );
                    console.log(`[Story Mode ${storyModel}] Episode ${i + 1} attempt ${attempt} response:`, { success: data.success, hasVideoUrl: !!data.video_url, error: data.error });

                    if (data.success && data.video_url) {
                        break; // Success!
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

            // Close WebSocket after each episode
            if (wsRef.current) {
                wsRef.current.close();
            }
        }

        // Add all to series with custom name
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
        // NOTE: Prompts are NOT cleared - user can edit and regenerate
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
            <div className="container mx-auto p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <Link href="/" className="text-purple-300 hover:text-purple-100 transition-colors">
                        ← Back
                    </Link>
                    <h1 className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 text-transparent bg-clip-text">
                        AI Video Factory
                    </h1>
                    <div className="w-16"></div>
                </div>

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
                                Single Episode
                            </button>
                            <button
                                onClick={() => setMode('batch')}
                                className={`px-4 py-2 rounded-lg font-medium transition-all ${mode === 'batch'
                                    ? 'bg-purple-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                Batch Episodes
                            </button>
                            <button
                                onClick={() => setMode('story')}
                                className={`px-4 py-2 rounded-lg font-medium transition-all ${mode === 'story'
                                    ? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                Story Mode
                            </button>
                        </div>

                        {/* Reference Image - Only for Single and Story modes (not used in Batch) */}
                        {mode !== 'batch' && (
                        <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                                <Camera className="w-4 h-4" /> Reference Image{mode === 'story' && storyModel === 'veo31' ? 's' : ''}
                                {mode === 'story' ? (
                                    storyModel === 'veo31' ? (
                                        <span className="text-purple-400 text-sm">(Up to 3 for R2V)</span>
                                    ) : (
                                        <span className="text-purple-400 text-sm">(Character for all episodes)</span>
                                    )
                                ) : (
                                    <span className="text-gray-500 text-sm">(Optional)</span>
                                )}
                            </h3>
                            {(mode === 'single' && model === 'veo3') ? (
                                <div className="text-gray-400 text-sm p-4 bg-black/20 rounded-lg border border-white/5">
                                    <AlertTriangle className="w-4 h-4 inline mr-2 text-yellow-500" />
                                    Veo 3 does not support image-to-video. Switch to <span className="text-purple-400">Kling AI</span> to use reference images.
                                </div>
                            ) : mode === 'story' && storyModel === 'veo31' ? (
                                /* Veo 3.1 R2V: Multiple reference images (up to 3) */
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
                                        Upload 1-3 reference images for character consistency. R2V works best with clear face shots.
                                    </p>
                                </div>
                            ) : (
                                /* MiniMax S2V or Single/Batch modes: Single reference image */
                                <>
                                    <ImageUpload
                                        apiBaseUrl={API_BASE_URL}
                                        onImageUploaded={(url) => {
                                            setReferenceImageUrl(url);
                                            // In Story Mode, also set as character image
                                            if (mode === 'story') {
                                                setCharacterImageUrl(url);
                                                setCharacterName('Custom Character');
                                                setCharacterDescription('User-uploaded reference image');
                                            }
                                        }}
                                        onImageRemoved={() => {
                                            setReferenceImageUrl(null);
                                            // In Story Mode, clear character image if it was the uploaded one
                                            if (mode === 'story' && characterName === 'Custom Character') {
                                                setCharacterImageUrl(null);
                                                setCharacterName('');
                                                setCharacterDescription('');
                                            }
                                        }}
                                    />
                                    {mode === 'story' && (
                                        <p className="text-gray-500 text-xs mt-2">
                                            Upload your character image to maintain consistent appearance across all episodes.
                                            {!referenceImageUrl && ' Or generate prompts first to auto-generate a character.'}
                                        </p>
                                    )}
                                </>
                            )}
                        </div>
                        )}

                        {/* Single Mode */}
                        {mode === 'single' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><PenLine className="w-4 h-4" /> Prompt</h3>
                                <textarea
                                    value={prompt}
                                    onChange={(e) => setPrompt(e.target.value)}
                                    placeholder="A beautiful woman walks through neon-lit Tokyo streets at night..."
                                    className="w-full h-32 bg-black/30 border border-white/10 rounded-lg p-3 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-purple-500"
                                />
                            </div>
                        )}

                        {/* Batch Mode */}
                        {mode === 'batch' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <div className="flex justify-between items-center mb-3">
                                    <h3 className="text-white font-medium flex items-center gap-2"><PenLine className="w-4 h-4" /> Episode Prompts</h3>
                                    <button
                                        onClick={addBatchPrompt}
                                        className="text-purple-400 hover:text-purple-300 text-sm"
                                    >
                                        + Add Episode
                                    </button>
                                </div>
                                <div className="space-y-3">
                                    {batchPrompts.map((p, i) => (
                                        <div key={i} className="flex gap-2">
                                            <span className="text-gray-500 mt-2 w-6">{i + 1}.</span>
                                            <textarea
                                                value={p}
                                                onChange={(e) => updateBatchPrompt(i, e.target.value)}
                                                placeholder={`Episode ${i + 1} prompt...`}
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
                                        <Sparkles className="w-4 h-4" /> Story Idea
                                    </h3>
                                    <textarea
                                        value={storyIdea}
                                        onChange={(e) => setStoryIdea(e.target.value)}
                                        placeholder="Describe your story idea... e.g., 'A detective investigates mysterious disappearances in a small coastal town'"
                                        className="w-full h-24 bg-black/30 border border-white/10 rounded-lg p-3 text-white placeholder-gray-500 resize-none focus:outline-none focus:border-purple-500"
                                    />

                                    <div className="grid grid-cols-3 gap-4 mt-4">
                                        <div>
                                            <label className="text-gray-400 text-sm mb-1 block">Genre</label>
                                            <select
                                                value={storyGenre}
                                                onChange={(e) => setStoryGenre(e.target.value)}
                                                className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                            >
                                                <option value="drama">Drama</option>
                                                <option value="comedy">Comedy</option>
                                                <option value="thriller">Thriller</option>
                                                <option value="fantasy">Fantasy</option>
                                                <option value="romance">Romance</option>
                                                <option value="action">Action</option>
                                                <option value="horror">Horror</option>
                                                <option value="scifi">Sci-Fi</option>
                                                <option value="mystery">Mystery</option>
                                                <option value="melodrama">Melodrama</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="text-gray-400 text-sm mb-1 block">AI Model</label>
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
                                            <label className="text-gray-400 text-sm mb-1 block">Episodes: {storyEpisodesCount}</label>
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
                                                Generating prompts...
                                            </>
                                        ) : (
                                            <>
                                                <Sparkles className="w-4 h-4" /> Generate Episode Prompts
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
                                            <span className="text-gray-500 text-sm">{generatedEpisodes.length} episodes</span>
                                        </div>
                                        {seriesLogline && (
                                            <p className="text-gray-400 text-sm mb-4 italic">{seriesLogline}</p>
                                        )}

                                        <div className="space-y-3 max-h-96 overflow-y-auto">
                                            {generatedEpisodes.map((ep, i) => (
                                                <div key={i} className="bg-black/30 rounded-lg p-3">
                                                    <div className="flex justify-between items-center mb-2">
                                                        <span className="text-purple-400 font-medium text-sm">
                                                            Episode {ep.number}: {ep.title}
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

                                {/* Character Preview (after generating prompts) */}
                                {characterImageUrl && (
                                    <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                        <div className="flex items-center justify-between mb-3">
                                            <h3 className="text-white font-medium flex items-center gap-2">
                                                <User className="w-4 h-4" /> Main Character
                                            </h3>
                                            <label className="flex items-center gap-2 text-sm cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={isConsistencyEnabled}
                                                    onChange={(e) => setIsConsistencyEnabled(e.target.checked)}
                                                    className="w-4 h-4 rounded bg-black/30 border-white/20 text-purple-500 focus:ring-purple-500"
                                                />
                                                <span className="text-gray-400">Character Consistency</span>
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
                                                    {characterDescription || 'This character will appear consistently across all episodes.'}
                                                </p>
                                                {isConsistencyEnabled ? (
                                                    <p className="text-green-400 text-xs mt-2 flex items-center gap-1">
                                                        <Link2 className="w-3 h-3" /> {MODEL_CONFIG[storyModel].name}: {MODEL_CONFIG[storyModel].consistencyNote}
                                                    </p>
                                                ) : (
                                                    <p className="text-yellow-400 text-xs mt-2 flex items-center gap-1">
                                                        <AlertTriangle className="w-3 h-3" /> Consistency disabled - characters may vary
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Settings - Only for Single/Batch modes (Story Mode has settings built into AI Model selector) */}
                        {mode !== 'story' && (
                            <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10">
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><Settings className="w-4 h-4" /> Settings</h3>
                                <div className="grid grid-cols-3 gap-4">
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">Duration</label>
                                        <select
                                            value={duration}
                                            onChange={(e) => setDuration(parseInt(e.target.value))}
                                            className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                        >
                                            <option value={4} className="bg-gray-800 text-white">4 seconds</option>
                                            <option value={6} className="bg-gray-800 text-white">6 seconds</option>
                                            <option value={8} className="bg-gray-800 text-white">8 seconds</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">Aspect Ratio</label>
                                        <select
                                            value={aspectRatio}
                                            onChange={(e) => setAspectRatio(e.target.value)}
                                            className="w-full bg-gray-800 border border-white/10 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500 font-sans"
                                        >
                                            <option value="9:16" className="bg-gray-800 text-white">9:16 (Vertical)</option>
                                            <option value="16:9" className="bg-gray-800 text-white">16:9 (Horizontal)</option>
                                            {model === 'kling' && (
                                                <option value="1:1" className="bg-gray-800 text-white">1:1 (Square)</option>
                                            )}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-gray-400 text-sm mb-1 block">AI Model</label>
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
                                        ? `Episode ${batchProgress.current}/${batchProgress.total}`
                                        : 'Generating...'
                                    }
                                </span>
                            ) : (
                                <span className="flex items-center justify-center gap-2">
                                    <Play className="w-5 h-5" />
                                    {mode === 'single'
                                        ? 'Generate Episode'
                                        : mode === 'batch'
                                            ? `Generate ${batchPrompts.filter(p => p.trim()).length} Episodes`
                                            : `Generate ${generatedEpisodes.length} Story Episodes`
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
                                    Stage: {generationProgress.stage}
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
                                <h3 className="text-white font-medium mb-3 flex items-center gap-2"><Play className="w-4 h-4" /> Latest Generation</h3>
                                <video
                                    src={result.video_url}
                                    controls
                                    autoPlay
                                    loop
                                    muted
                                    className="w-full max-w-sm rounded-lg mx-auto"
                                />
                            </div>
                        )}
                    </div>

                    {/* Right Column - Series Panel */}
                    <div className="bg-white/5 backdrop-blur rounded-xl p-4 border border-white/10 h-fit mt-16">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-white font-medium flex items-center gap-2"><Film className="w-4 h-4" /> Series</h3>
                            <button
                                onClick={createNewSeries}
                                className="text-purple-400 hover:text-purple-300 text-sm"
                            >
                                + New
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
                                <p className="text-sm">Generated episodes</p>
                                <p className="text-sm">will appear here</p>
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
                                        Merging...
                                    </span>
                                ) : (
                                    <span className="flex items-center justify-center gap-2"><Download className="w-4 h-4" /> Merge & Download Series</span>
                                )}
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
