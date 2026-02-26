'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createReviewItem,
  generateEpisodeClip,
  generateSeriesPlan,
  mergeVideos,
  GenerationModel,
} from '@/lib/api/generation';
import { API_V1_BASE_URL } from '@/lib/apiBase';
import { safeJsonParse } from '@/lib/safeJson';
import { useLanguage } from '@/contexts/LanguageContext';
import { EpisodeDraft, FlowStep, FlowStepId, GenerationDraftSnapshot, IdeaFormState, PublishFormState } from './types';

const DRAFT_STORAGE_KEY = 'ai_video_factory_generate_v2_draft';

const STEP_ORDER: FlowStepId[] = ['idea', 'episodes', 'generation', 'publish'];
const SINGLE_EPISODE_MODELS: GenerationModel[] = ['veo3', 'kling'];
const SERIES_MODELS: GenerationModel[] = ['minimax', 'veo31'];
const MODEL_DURATIONS: Record<GenerationModel, number[]> = {
  veo3: [4, 6, 8],
  veo31: [4, 6, 8],
  kling: [5, 10],
  minimax: [6],
};

const DEFAULT_IDEA_FORM: IdeaFormState = {
  idea: '',
  genre: 'drama',
  episodesCount: 4,
  duration: 6,
  aspectRatio: '9:16',
  model: 'minimax',
};

const DEFAULT_PUBLISH_FORM: PublishFormState = {
  selectedEpisodeId: '',
  title: '',
  description: '',
  tagsCsv: '',
};

function createEpisodeId(number: number): string {
  return `ep-${number}-${Math.random().toString(36).slice(2, 8)}`;
}

function updateEpisodeById(episodes: EpisodeDraft[], id: string, patch: Partial<EpisodeDraft>): EpisodeDraft[] {
  return episodes.map((episode) => (episode.id === id ? { ...episode, ...patch } : episode));
}

function normalizeEpisodesCount(value: number): number {
  if (!Number.isFinite(value)) return 1;
  return Math.min(10, Math.max(1, Math.round(value)));
}

function pickDefaultModelForCount(episodesCount: number): GenerationModel {
  return episodesCount > 1 ? 'minimax' : 'veo3';
}

function normalizeModelForCount(model: GenerationModel, episodesCount: number): GenerationModel {
  const allowedModels = episodesCount > 1 ? SERIES_MODELS : SINGLE_EPISODE_MODELS;
  return allowedModels.includes(model) ? model : pickDefaultModelForCount(episodesCount);
}

function normalizeDurationForModel(duration: number, model: GenerationModel): number {
  const allowedDurations = MODEL_DURATIONS[model];
  if (!Number.isFinite(duration)) return allowedDurations[0];
  return allowedDurations.includes(duration)
    ? duration
    : allowedDurations.reduce((prev, curr) => (Math.abs(curr - duration) < Math.abs(prev - duration) ? curr : prev));
}

function normalizeIdeaForm(value?: Partial<IdeaFormState> | null): IdeaFormState {
  const merged: IdeaFormState = {
    ...DEFAULT_IDEA_FORM,
    ...(value || {}),
  };
  const episodesCount = normalizeEpisodesCount(merged.episodesCount);
  const model = normalizeModelForCount(merged.model, episodesCount);
  return {
    ...merged,
    episodesCount,
    model,
    duration: normalizeDurationForModel(merged.duration, model),
  };
}

const VALID_GENRES = ['drama', 'thriller', 'comedy', 'romance', 'mystery', 'scifi', 'action'];

function normalizeGenre(genre: string): string {
  const lower = genre.toLowerCase();
  if (VALID_GENRES.includes(lower)) return lower;
  return 'drama';
}

export function useGenerationFlow() {
  const { t } = useLanguage();
  const searchParams = useSearchParams();
  const [currentStep, setCurrentStep] = useState<FlowStepId>('idea');
  const [ideaForm, setIdeaForm] = useState<IdeaFormState>(DEFAULT_IDEA_FORM);
  const [seriesTitle, setSeriesTitle] = useState('');
  const [seriesLogline, setSeriesLogline] = useState('');
  const [episodes, setEpisodes] = useState<EpisodeDraft[]>([]);
  const [publishForm, setPublishForm] = useState<PublishFormState>(DEFAULT_PUBLISH_FORM);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isStitching, setIsStitching] = useState(false);
  const [stitchedVideoUrl, setStitchedVideoUrl] = useState<string | null>(null);
  const [stitchedDuration, setStitchedDuration] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const hydratedRef = useRef(false);
  const projectLoadedRef = useRef(false);

  // Load project from ?project=N URL parameter
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const projectParam = searchParams.get('project');
    if (!projectParam || projectLoadedRef.current) return;
    projectLoadedRef.current = true;

    const pid = parseInt(projectParam, 10);
    if (isNaN(pid)) return;

    // Clear localStorage draft to avoid conflicts
    localStorage.removeItem(DRAFT_STORAGE_KEY);

    fetch(`${API_V1_BASE_URL}/projects/${pid}`)
      .then((res) => {
        if (!res.ok) throw new Error('Project not found');
        return res.json();
      })
      .then((data) => {
        setProjectId(data.id);
        setIdeaForm(
          normalizeIdeaForm({
            idea: data.logline || '',
            genre: normalizeGenre(data.genre || 'drama'),
            episodesCount: data.total_episodes || 1,
          }),
        );
        setSeriesTitle(data.title || '');
        setSeriesLogline(data.logline || '');
        setEpisodes([]);
        setCurrentStep('idea');

        // Pre-fill publish form with SEO data
        const tags = safeJsonParse<string[]>(data.seo_tags_json, []);
        setPublishForm({
          selectedEpisodeId: '',
          title: data.seo_title || data.title || '',
          description: data.seo_description || '',
          tagsCsv: tags.join(', '),
        });

        hydratedRef.current = true;
      })
      .catch(() => {
        hydratedRef.current = true;
      });
  }, [searchParams]);

  // Load from localStorage (only if no project param)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (searchParams.get('project')) return; // skip if loading project
    const snapshot = safeJsonParse<GenerationDraftSnapshot | null>(
      localStorage.getItem(DRAFT_STORAGE_KEY),
      null,
    );
    if (snapshot) {
      setIdeaForm(normalizeIdeaForm(snapshot.ideaForm));
      setEpisodes(Array.isArray(snapshot.episodes) ? snapshot.episodes : []);
      setSeriesTitle(snapshot.seriesTitle || '');
      setSeriesLogline(snapshot.seriesLogline || '');
      setCurrentStep(snapshot.currentStep || 'idea');
    }
    hydratedRef.current = true;
  }, [searchParams]);

  useEffect(() => {
    if (!hydratedRef.current || typeof window === 'undefined') return;
    const snapshot: GenerationDraftSnapshot = {
      currentStep,
      ideaForm,
      episodes,
      seriesTitle,
      seriesLogline,
    };
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(snapshot));
  }, [currentStep, episodes, ideaForm, seriesLogline, seriesTitle]);

  const steps = useMemo<FlowStep[]>(
    () =>
      STEP_ORDER.map((id) => {
        if (id === 'idea') {
          return {
            id,
            label: t('generateV2.stepIdeaLabel'),
            hint: t('generateV2.stepIdeaHint'),
          };
        }
        if (id === 'episodes') {
          return {
            id,
            label: t('generateV2.stepEpisodesLabel'),
            hint: t('generateV2.stepEpisodesHint'),
          };
        }
        if (id === 'generation') {
          return {
            id,
            label: t('generateV2.stepGenerationLabel'),
            hint: t('generateV2.stepGenerationHint'),
          };
        }
        return {
          id,
          label: t('generateV2.stepPublishLabel'),
          hint: t('generateV2.stepPublishHint'),
        };
      }),
    [t],
  );

  const stats = useMemo(() => {
    const done = episodes.filter((e) => e.status === 'done').length;
    const generating = episodes.filter((e) => e.status === 'generating').length;
    const failed = episodes.filter((e) => e.status === 'error').length;
    const queued = episodes.filter((e) => e.status === 'queued').length;
    return { done, generating, failed, queued, total: episodes.length };
  }, [episodes]);

  const selectedEpisode = useMemo(
    () => episodes.find((episode) => episode.id === publishForm.selectedEpisodeId),
    [episodes, publishForm.selectedEpisodeId],
  );

  const updateIdeaForm = useCallback(<K extends keyof IdeaFormState>(key: K, value: IdeaFormState[K]) => {
    setIdeaForm((prev) => {
      const next = { ...prev, [key]: value };

      if (key === 'episodesCount') {
        const normalizedEpisodesCount = normalizeEpisodesCount(Number(value));
        const normalizedModel = normalizeModelForCount(prev.model, normalizedEpisodesCount);
        return {
          ...next,
          episodesCount: normalizedEpisodesCount,
          model: normalizedModel,
          duration: normalizeDurationForModel(prev.duration, normalizedModel),
        };
      }

      if (key === 'model') {
        const normalizedModel = normalizeModelForCount(value as GenerationModel, prev.episodesCount);
        return {
          ...next,
          model: normalizedModel,
          duration: normalizeDurationForModel(prev.duration, normalizedModel),
        };
      }

      if (key === 'duration') {
        return {
          ...next,
          duration: normalizeDurationForModel(Number(value), prev.model),
        };
      }

      return next;
    });
  }, []);

  const updateEpisodeField = useCallback(
    <K extends keyof EpisodeDraft>(id: string, key: K, value: EpisodeDraft[K]) => {
      setEpisodes((prev) => updateEpisodeById(prev, id, { [key]: value }));
    },
    [],
  );

  const goStep = useCallback((step: FlowStepId) => {
    setCurrentStep(step);
    setError(null);
    setNotice(null);
  }, []);

  const resetFlow = useCallback(() => {
    setCurrentStep('idea');
    setIdeaForm(DEFAULT_IDEA_FORM);
    setSeriesTitle('');
    setSeriesLogline('');
    setEpisodes([]);
    setPublishForm(DEFAULT_PUBLISH_FORM);
    setError(null);
    setNotice(null);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
  }, []);

  const planEpisodes = useCallback(async () => {
    setError(null);
    setNotice(null);
    if (ideaForm.idea.trim().length < 10) {
      setError(t('generateV2.errorIdeaTooShort'));
      return;
    }

    setIsPlanning(true);
    try {
      const response = await generateSeriesPlan({
        idea: ideaForm.idea.trim(),
        genre: ideaForm.genre,
        episodes_count: ideaForm.episodesCount,
        duration: ideaForm.duration,
        aspect_ratio: ideaForm.aspectRatio,
      });

      if (!response.success) {
        throw new Error(response.error || t('generateV2.errorGenerateEpisodes'));
      }

      const nextEpisodes = (response.episodes || []).map((episode) => ({
        id: createEpisodeId(episode.number),
        number: episode.number,
        title: episode.title,
        synopsis: episode.synopsis,
        prompt: episode.prompt,
        status: 'queued' as const,
      }));

      setSeriesTitle(response.series_title || t('generateV2.untitledSeries'));
      setSeriesLogline(response.logline || '');
      setEpisodes(nextEpisodes);
      setPublishForm(DEFAULT_PUBLISH_FORM);
      setCurrentStep('episodes');
      setNotice(t('generateV2.noticeGeneratedPrompts', { count: nextEpisodes.length }));
    } catch (planError) {
      setError(planError instanceof Error ? planError.message : t('generateV2.errorGenerateEpisodes'));
    } finally {
      setIsPlanning(false);
    }
  }, [ideaForm, t]);

  const runEpisodeGeneration = useCallback(
    async (episodeId: string): Promise<boolean> => {
      const episode = episodes.find((item) => item.id === episodeId);
      if (!episode) return false;
      if (!episode.prompt.trim()) {
        setEpisodes((prev) => updateEpisodeById(prev, episodeId, { status: 'error', error: t('generateV2.errorPromptEmpty') }));
        return false;
      }

      setEpisodes((prev) => updateEpisodeById(prev, episodeId, { status: 'generating', error: undefined }));
      try {
        const response = await generateEpisodeClip({
          prompt: episode.prompt.trim(),
          duration: ideaForm.duration,
          aspect_ratio: ideaForm.aspectRatio,
          model: ideaForm.model as GenerationModel,
        });

        if (!response.success || !response.video_url) {
          throw new Error(response.error || t('generateV2.errorNoVideoUrl'));
        }

        setEpisodes((prev) =>
          updateEpisodeById(prev, episodeId, {
            status: 'done',
            videoUrl: response.video_url,
            error: undefined,
          }),
        );
        return true;
      } catch (generationError) {
        setEpisodes((prev) =>
          updateEpisodeById(prev, episodeId, {
            status: 'error',
            error: generationError instanceof Error ? generationError.message : t('generateV2.errorGenerationFailed'),
          }),
        );
        return false;
      }
    },
    [episodes, ideaForm.aspectRatio, ideaForm.duration, ideaForm.model, t],
  );

  const runQueue = useCallback(async () => {
    setError(null);
    setNotice(null);
    setCurrentStep('generation');
    setIsGenerating(true);
    try {
      let hasSuccess = false;
      const queue = episodes.map((episode) => episode.id);
      for (const episodeId of queue) {
        const ok = await runEpisodeGeneration(episodeId);
        if (ok) hasSuccess = true;
      }

      if (hasSuccess) {
        setCurrentStep('publish');
      }
    } finally {
      setIsGenerating(false);
    }
  }, [episodes, runEpisodeGeneration]);

  const retryEpisode = useCallback(
    async (episodeId: string) => {
      setError(null);
      setNotice(null);
      await runEpisodeGeneration(episodeId);
    },
    [runEpisodeGeneration],
  );

  const removeEpisode = useCallback((episodeId: string) => {
    setEpisodes((prev) => prev.filter((episode) => episode.id !== episodeId));
    setPublishForm((prev) =>
      prev.selectedEpisodeId === episodeId
        ? {
            ...prev,
            selectedEpisodeId: '',
          }
        : prev,
    );
  }, []);

  const selectPublishEpisode = useCallback(
    (episodeId: string) => {
      const episode = episodes.find((item) => item.id === episodeId);
      setPublishForm((prev) => ({
        ...prev,
        selectedEpisodeId: episodeId,
        title: episode?.title || prev.title,
        description: episode?.synopsis || prev.description,
      }));
    },
    [episodes],
  );

  const updatePublishForm = useCallback(<K extends keyof PublishFormState>(key: K, value: PublishFormState[K]) => {
    setPublishForm((prev) => ({ ...prev, [key]: value }));
  }, []);

  const stitchEpisodes = useCallback(async () => {
    setError(null);
    setNotice(null);
    const readyEpisodes = episodes.filter((e) => e.status === 'done' && e.videoUrl);
    if (readyEpisodes.length < 2) {
      setError(t('generateV2.errorNoReadyEpisodes'));
      return;
    }

    const videoUrls = readyEpisodes.map((e) => e.videoUrl!);
    setIsStitching(true);
    try {
      const response = await mergeVideos({ video_urls: videoUrls });
      if (!response.success || !response.merged_video_url) {
        throw new Error(response.error || t('generateV2.errorStitchFailed'));
      }
      setStitchedVideoUrl(response.merged_video_url);
      setStitchedDuration(response.total_duration ?? null);
      setPublishForm((prev) => ({
        ...prev,
        title: prev.title || seriesTitle,
        description: prev.description || seriesLogline,
      }));
      setNotice(t('generateV2.stitched'));
    } catch (stitchError) {
      setError(stitchError instanceof Error ? stitchError.message : t('generateV2.errorStitchFailed'));
    } finally {
      setIsStitching(false);
    }
  }, [episodes, seriesTitle, seriesLogline, t]);

  const publishToReview = useCallback(async () => {
    setError(null);
    setNotice(null);

    const videoUrl = stitchedVideoUrl;
    const episode = episodes.find((item) => item.id === publishForm.selectedEpisodeId);

    if (!videoUrl && (!episode || !episode.videoUrl)) {
      setError(t('generateV2.errorChooseEpisode'));
      return;
    }

    const tags = publishForm.tagsCsv
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);

    setIsPublishing(true);
    try {
      await createReviewItem({
        video_url: videoUrl || episode!.videoUrl!,
        title: publishForm.title.trim() || seriesTitle || episode?.title || '',
        description: publishForm.description.trim() || seriesLogline || episode?.synopsis || '',
        tags,
        project_id: projectId,
      });
      setNotice(t('generateV2.noticeSentToReview'));
    } catch (publishError) {
      setError(publishError instanceof Error ? publishError.message : t('generateV2.errorSendToReview'));
    } finally {
      setIsPublishing(false);
    }
  }, [episodes, publishForm, stitchedVideoUrl, seriesTitle, seriesLogline, projectId, t]);

  return {
    steps,
    currentStep,
    ideaForm,
    seriesTitle,
    seriesLogline,
    episodes,
    publishForm,
    selectedEpisode,
    isPlanning,
    isGenerating,
    isPublishing,
    isStitching,
    stitchedVideoUrl,
    stitchedDuration,
    error,
    notice,
    stats,
    updateIdeaForm,
    updateEpisodeField,
    goStep,
    resetFlow,
    planEpisodes,
    runQueue,
    retryEpisode,
    removeEpisode,
    selectPublishEpisode,
    updatePublishForm,
    stitchEpisodes,
    publishToReview,
  };
}
