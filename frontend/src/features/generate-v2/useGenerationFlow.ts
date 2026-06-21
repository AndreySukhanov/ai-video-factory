'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  createReviewItem,
  extractLastFrame,
  generateEpisodeClip,
  generateSeriesPlan,
  generateStoryboard,
  regenerateStoryboardFrame,
  mergeVideos,
  GenerationModel,
  ImageModel,
  FrameAuditReport,
} from '@/lib/api/generation';
import { API_V1_BASE_URL } from '@/lib/apiBase';
import { safeJsonParse } from '@/lib/safeJson';
import { useLanguage } from '@/contexts/LanguageContext';
import { EpisodeDraft, FlowStep, FlowStepId, GenerationDraftSnapshot, IdeaFormState, PublishFormState } from './types';

const DRAFT_STORAGE_KEY = 'ai_video_factory_generate_v2_draft';

const STEP_ORDER: FlowStepId[] = ['idea', 'episodes', 'storyboard', 'generation', 'publish'];
const SINGLE_EPISODE_MODELS: GenerationModel[] = ['wavespeed', 'wavespeed-standard', 'wavespeed-v15', 'laozhang', 'vertex', 'kling'];
const SERIES_MODELS: GenerationModel[] = ['wavespeed', 'wavespeed-standard', 'wavespeed-v15', 'laozhang', 'vertex', 'minimax'];
const MODEL_DURATIONS: Record<GenerationModel, number[]> = {
  kling: [5, 10],
  minimax: [6],
  laozhang: [4, 6, 8],
  gemini: [4, 6, 8],
  vertex: [4, 6, 8],
  wavespeed: [4, 5, 8, 10, 15],
  'wavespeed-standard': [4, 5, 8, 10, 15],
  'wavespeed-v15': [5, 10],
  fal: [5, 10],
};

// Veo 3.1 does NOT support 1:1 aspect ratio
const VEO31_ALLOWED_ASPECTS = ['9:16', '16:9'];

const DEFAULT_IDEA_FORM: IdeaFormState = {
  idea: '',
  genre: 'drama',
  episodesCount: 4,
  duration: 6,
  aspectRatio: '9:16',
  model: 'laozhang',
  llmModel: 'opus-4.8',
  generateAudio: true,
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
  return episodesCount > 1 ? 'laozhang' : 'laozhang';
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

function normalizeAspectForModel(aspectRatio: string, model: GenerationModel): string {
  // Veo 3.1 / LaoZhang does not support 1:1
  if ((model === 'laozhang' || model === 'gemini' || model === 'vertex') && !VEO31_ALLOWED_ASPECTS.includes(aspectRatio)) {
    return '9:16';
  }
  return aspectRatio;
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
    aspectRatio: normalizeAspectForModel(merged.aspectRatio, model),
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
  const [isStoryboarding, setIsStoryboarding] = useState(false);
  const [storyboardFrames, setStoryboardFrames] = useState<string[]>([]);
  const [storyboardAudit, setStoryboardAudit] = useState<FrameAuditReport[]>([]);
  const [storyboardSeed, setStoryboardSeed] = useState<number | null>(null);
  const [imageModel, setImageModel] = useState<ImageModel>('gemini');
  const [referenceImages, setReferenceImages] = useState<string[]>([]);
  const [referenceLocalUrls, setReferenceLocalUrls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const hydratedRef = useRef(false);
  const projectLoadedRef = useRef(false);
  const pendingOverridesRef = useRef<Array<{ number: number; model?: string; duration?: number }>>([]);

  // Ref to always have fresh episodes (avoids stale closure in sequential queue)
  const episodesRef = useRef(episodes);
  useEffect(() => { episodesRef.current = episodes; }, [episodes]);

  // Veo 3.1 series metadata
  const [characterCard, setCharacterCard] = useState<string | null>(null);
  const [voiceDescription, setVoiceDescription] = useState<string | null>(null);
  const [anchorPrompt, setAnchorPrompt] = useState<string | null>(null);

  // Phase 3: prefill from /trends "Сделать похожее" button.
  // Trends page stashes the clone-brief in sessionStorage and navigates here with ?source=clone.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (searchParams.get('source') !== 'clone') return;
    if (projectLoadedRef.current) return;
    projectLoadedRef.current = true;

    let raw: string | null = null;
    try { raw = sessionStorage.getItem('clone_brief'); } catch { return; }
    if (!raw) return;

    try {
      const brief = JSON.parse(raw);
      localStorage.removeItem(DRAFT_STORAGE_KEY);

      setIdeaForm(normalizeIdeaForm({
        idea: brief.idea || '',
        genre: normalizeGenre(brief.genre || 'drama'),
        episodesCount: brief.episodes_count || 5,
        duration: brief.duration || 6,
        aspectRatio: brief.aspect_ratio || '9:16',
      }));

      if (brief.anchor_prompt) setAnchorPrompt(brief.anchor_prompt);
      if (brief.character_card) setCharacterCard(brief.character_card);
      if (brief.suggested_title) setSeriesTitle(brief.suggested_title);

      // Pre-fill episode drafts from brief.episodes (derived from story_beats by
      // /clone-brief). This skips the "Plan series" LLM step — beats are already
      // structured, so we go straight to /generate ready to render.
      if (Array.isArray(brief.episodes) && brief.episodes.length > 0) {
        type BriefEp = { number: number; title: string; synopsis: string; prompt: string };
        const drafts: EpisodeDraft[] = (brief.episodes as BriefEp[]).map((ep) => ({
          id: createEpisodeId(ep.number),
          number: ep.number,
          title: ep.title,
          synopsis: ep.synopsis,
          prompt: ep.prompt,
          status: 'queued' as const,
          anchorPrompt: brief.anchor_prompt,
        }));
        setEpisodes(drafts);
        // Episodes ready — jump straight to the Episodes step
        setCurrentStep('episodes');
      } else {
        setCurrentStep('idea');
      }

      hydratedRef.current = true;
      // Consume the brief so a page reload doesn't re-prefill
      try { sessionStorage.removeItem('clone_brief'); } catch { /* ignore */ }
    } catch (e) {
      console.warn('[clone-brief] failed to parse stashed brief:', e);
    }
  }, [searchParams]);

  // Load project from ?project=N URL parameter
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const projectParam = searchParams.get('project');
    if (!projectParam || projectLoadedRef.current) return;
    projectLoadedRef.current = true;

    const pid = parseInt(projectParam, 10);
    if (isNaN(pid)) return;

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

  // Load from localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (searchParams.get('project')) return;
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
      setCharacterCard(snapshot.characterCard || null);
      setVoiceDescription(snapshot.voiceDescription || null);
      setAnchorPrompt(snapshot.anchorPrompt || null);
      setStoryboardFrames(Array.isArray(snapshot.storyboardFrames) ? snapshot.storyboardFrames : []);
      setReferenceImages(Array.isArray(snapshot.referenceImages) ? snapshot.referenceImages : []);
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
      characterCard: characterCard || undefined,
      voiceDescription: voiceDescription || undefined,
      anchorPrompt: anchorPrompt || undefined,
      storyboardFrames: storyboardFrames.length > 0 ? storyboardFrames : undefined,
      referenceImages: referenceImages.length > 0 ? referenceImages : undefined,
    };
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(snapshot));
  }, [currentStep, episodes, ideaForm, seriesLogline, seriesTitle, characterCard, voiceDescription, anchorPrompt, storyboardFrames, referenceImages]);

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
        if (id === 'storyboard') {
          return {
            id,
            label: t('generateV2.stepStoryboardLabel'),
            hint: t('generateV2.stepStoryboardHint'),
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
          aspectRatio: normalizeAspectForModel(prev.aspectRatio, normalizedModel),
        };
      }

      if (key === 'model') {
        const normalizedModel = normalizeModelForCount(value as GenerationModel, prev.episodesCount);
        return {
          ...next,
          model: normalizedModel,
          duration: normalizeDurationForModel(prev.duration, normalizedModel),
          aspectRatio: normalizeAspectForModel(prev.aspectRatio, normalizedModel),
        };
      }

      if (key === 'duration') {
        return {
          ...next,
          duration: normalizeDurationForModel(Number(value), prev.model),
        };
      }

      if (key === 'aspectRatio') {
        return {
          ...next,
          aspectRatio: normalizeAspectForModel(value as string, prev.model),
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

  const setEpisodeModel = useCallback((id: string, model: GenerationModel | null) => {
    setEpisodes((prev) =>
      prev.map((ep) => {
        if (ep.id !== id) return ep;
        if (model === null) {
          // reset to default (drop override fields so it falls back to ideaForm.model)
          const next = { ...ep };
          delete next.model;
          delete next.duration;
          return next;
        }
        const allowedDurations = MODEL_DURATIONS[model];
        const currentDuration = ep.duration ?? allowedDurations[0];
        const normalizedDuration = allowedDurations.includes(currentDuration)
          ? currentDuration
          : allowedDurations.reduce((prev, curr) =>
              Math.abs(curr - currentDuration) < Math.abs(prev - currentDuration) ? curr : prev,
            );
        return { ...ep, model, duration: normalizedDuration };
      }),
    );
  }, []);

  const dumpToTemplatePayload = useCallback(() => {
    return {
      version: 1,
      ideaForm: { ...ideaForm },
      episodeOverrides: episodes
        .filter((ep) => ep.model || ep.duration !== undefined)
        .map((ep) => ({
          number: ep.number,
          model: ep.model,
          duration: ep.duration,
        })),
      imageModel,
      storyboardSeed: storyboardSeed ?? null,
      anchorPromptHint: anchorPrompt || undefined,
    };
  }, [ideaForm, episodes, imageModel, storyboardSeed, anchorPrompt]);

  const applyTemplatePayload = useCallback((payload: unknown) => {
    if (!payload || typeof payload !== 'object') return;
    const p = payload as {
      version?: number;
      ideaForm?: Partial<IdeaFormState>;
      episodeOverrides?: Array<{ number: number; model?: string; duration?: number }>;
      imageModel?: string;
      storyboardSeed?: number | null;
    };
    if (p.version !== 1) {
      setError(t('generateV2.templateIncompatible') || 'Incompatible template version');
      return;
    }
    if (p.ideaForm) {
      setIdeaForm((prev) => normalizeIdeaForm({ ...prev, ...p.ideaForm }));
    }
    // Stash overrides to apply after planEpisodes (they need real episode IDs)
    if (p.episodeOverrides && p.episodeOverrides.length > 0) {
      pendingOverridesRef.current = p.episodeOverrides;
    }
    if (p.imageModel === 'gemini' || p.imageModel === 'seedream' || p.imageModel === 'flux') {
      setImageModel(p.imageModel);
    }
    if (p.storyboardSeed !== undefined && p.storyboardSeed !== null) {
      setStoryboardSeed(p.storyboardSeed);
    }
    setNotice(t('generateV2.templateApplied') || 'Template applied');
  }, [t]);

  const applyModelToAll = useCallback((model: GenerationModel) => {
    setEpisodes((prev) =>
      prev.map((ep) => {
        const allowedDurations = MODEL_DURATIONS[model];
        const currentDuration = ep.duration ?? allowedDurations[0];
        const normalizedDuration = allowedDurations.includes(currentDuration)
          ? currentDuration
          : allowedDurations[0];
        return { ...ep, model, duration: normalizedDuration };
      }),
    );
  }, []);

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
    setCharacterCard(null);
    setVoiceDescription(null);
    setAnchorPrompt(null);
    setStoryboardFrames([]);
    setReferenceImages([]);
    setReferenceLocalUrls([]);
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
        llm_model: ideaForm.llmModel ?? 'opus-4.8',
      });

      if (!response.success) {
        throw new Error(response.error || t('generateV2.errorGenerateEpisodes'));
      }

      // Store Veo 3.1 metadata
      setCharacterCard(response.character_card || null);
      setVoiceDescription(response.voice_description || null);
      setAnchorPrompt(response.anchor_prompt || null);

      const overrides = pendingOverridesRef.current;
      const nextEpisodes = (response.episodes || []).map((episode) => {
        const o = overrides.find((x) => x.number === episode.number);
        const draft: EpisodeDraft = {
          id: createEpisodeId(episode.number),
          number: episode.number,
          title: episode.title,
          synopsis: episode.synopsis,
          prompt: episode.prompt,
          status: 'queued' as const,
          anchorPrompt: episode.anchor_prompt,
          variablePrompt: episode.variable_prompt,
        };
        if (o?.model) draft.model = o.model as GenerationModel;
        if (o?.duration !== undefined) draft.duration = o.duration;
        return draft;
      });
      pendingOverridesRef.current = [];

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
      // Read fresh episodes from ref to avoid stale closure during sequential queue
      const freshEpisodes = episodesRef.current;
      const episode = freshEpisodes.find((item) => item.id === episodeId);
      if (!episode) return false;
      if (!episode.prompt.trim()) {
        setEpisodes((prev) => updateEpisodeById(prev, episodeId, { status: 'error', error: t('generateV2.errorPromptEmpty') }));
        return false;
      }

      setEpisodes((prev) => updateEpisodeById(prev, episodeId, { status: 'generating', error: undefined }));
      try {
        // Per-episode model/duration override (falls back to ideaForm)
        const effectiveModel = (episode.model ?? ideaForm.model) as GenerationModel;
        const effectiveDuration = episode.duration ?? ideaForm.duration;

        // === Reference image selection ===
        let referenceImageUrl: string | undefined;
        const isSeriesMode = ideaForm.episodesCount > 1;
        const supportsReferences = ['gemini', 'vertex', 'laozhang', 'wavespeed', 'wavespeed-standard', 'wavespeed-v15'].includes(effectiveModel);
        const storyboardFrame = storyboardFrames[episode.number - 1];

        // Priority 1: per-episode storyboard keyframe — used for EVERY episode that has one.
        // Each keyframe is anchored to the same character card + seed, so the character
        // stays consistent without drifting across frame-chain hops.
        if (storyboardFrame && supportsReferences) {
          referenceImageUrl = storyboardFrame;
          console.log(`[I2V] Using storyboard keyframe for episode ${episode.number}: ${storyboardFrame}`);
          setNotice(t('generateV2.usingStoryboardFrame', { count: episode.number }));
        }
        // Priority 2: Frame chaining for E2+ WITHOUT a keyframe (extract last frame from previous video)
        else if (isSeriesMode && supportsReferences && episode.number > 1) {
          const latestEpisodes = episodesRef.current;
          const prevEpisode = latestEpisodes.find((e) => e.number === episode.number - 1 && e.status === 'done' && e.videoUrl);
          if (prevEpisode?.videoUrl) {
            try {
              console.log(`[FRAME CHAIN] Extracting last frame from episode ${prevEpisode.number}...`);
              const frameResult = await extractLastFrame({ video_url: prevEpisode.videoUrl });
              if (frameResult.success && frameResult.frame_url) {
                referenceImageUrl = frameResult.frame_url;
                console.log(`[FRAME CHAIN] Got frame for episode ${episode.number}: ${frameResult.frame_url}`);
                setNotice(t('generateV2.frameChainingExtracted', { count: episode.number }));
              }
            } catch (frameErr) {
              console.warn('[FRAME CHAIN] Frame extraction failed, continuing without:', frameErr);
            }
          }
        }

        // Priority 3: User-uploaded reference photo for E1 (when no storyboard)
        if (!referenceImageUrl && supportsReferences && episode.number === 1) {
          const userRefs = referenceImages.filter((url) => url.trim());
          if (userRefs.length > 0) {
            referenceImageUrl = userRefs[0];
            console.log(`[I2V] Using uploaded reference photo for episode 1: ${userRefs[0]}`);
          }
        }

        // Duration: force 8s ONLY for Veo -fl frame-chaining fallback (those models need it).
        // Seedance/WaveSpeed keep the user-selected duration (v1.5 only allows 5/10).
        const isVeoFamily = ['gemini', 'vertex', 'laozhang'].includes(effectiveModel);
        const isFrameChainFallback = referenceImageUrl && !storyboardFrame && episode.number > 1;
        const duration = (isFrameChainFallback && isVeoFamily) ? 8 : effectiveDuration;

        // ALWAYS use full prompt — no motion-only replacement
        const promptText = episode.prompt.trim();

        // First/last frame override: if episode has explicit firstFrameUrl, use it
        const firstFrameUrl = episode.firstFrameUrl?.trim() || referenceImageUrl;
        const lastFrameUrl = episode.lastFrameUrl?.trim() || undefined;

        // Filter valid reference images
        const validRefImages = referenceImages.filter((url) => url.trim());

        // Single attempt — retry manually via "Повторить" button
        const response = await generateEpisodeClip({
          prompt: promptText,
          duration: lastFrameUrl ? 8 : duration, // transition mode forces 8s
          aspect_ratio: ideaForm.aspectRatio,
          model: effectiveModel,
          reference_image_url: firstFrameUrl,
          last_frame_image_url: lastFrameUrl,
          reference_images: validRefImages.length > 0 ? validRefImages : undefined,
          generate_audio: ideaForm.generateAudio,
        });

        if (!response.success || !response.video_url) {
          throw new Error(response.error || t('generateV2.errorNoVideoUrl'));
        }

        episodesRef.current = updateEpisodeById(episodesRef.current, episodeId, {
          status: 'done',
          videoUrl: response.video_url,
          error: undefined,
        });
        setEpisodes(episodesRef.current);
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
    [ideaForm.aspectRatio, ideaForm.duration, ideaForm.model, ideaForm.episodesCount, storyboardFrames, referenceImages, t],
  );

  const runQueue = useCallback(async () => {
    setError(null);
    setNotice(null);
    setCurrentStep('generation');
    setIsGenerating(true);
    try {
      let hasSuccess = false;
      // Only generate episodes that need generation (skip already done ones)
      const queue = episodes
        .filter((ep) => ep.status !== 'done' || !ep.videoUrl)
        .map((ep) => ep.id);
      // Count already-done episodes as success
      if (episodes.some((ep) => ep.status === 'done' && ep.videoUrl)) hasSuccess = true;
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

  const moveEpisode = useCallback((episodeId: string, direction: 'up' | 'down') => {
    setEpisodes((prev) => {
      const idx = prev.findIndex((ep) => ep.id === episodeId);
      if (idx < 0) return prev;
      const targetIdx = direction === 'up' ? idx - 1 : idx + 1;
      if (targetIdx < 0 || targetIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[targetIdx]] = [next[targetIdx], next[idx]];
      // Renumber after swap
      return next.map((ep, i) => ({ ...ep, number: i + 1 }));
    });
    // Invalidate stitched video since order changed
    setStitchedVideoUrl(null);
    setStitchedDuration(null);
  }, []);

  const regenerateEpisode = useCallback(
    async (episodeId: string) => {
      setError(null);
      setNotice(null);
      // Reset episode to queued, keeping the same prompt
      setEpisodes((prev) =>
        updateEpisodeById(prev, episodeId, { status: 'queued', videoUrl: undefined, error: undefined }),
      );
      episodesRef.current = episodesRef.current.map((ep) =>
        ep.id === episodeId ? { ...ep, status: 'queued' as const, videoUrl: undefined, error: undefined } : ep,
      );
      // Invalidate stitched video
      setStitchedVideoUrl(null);
      setStitchedDuration(null);
      // Run generation with the same prompt (character card, anchor prompt preserved)
      await runEpisodeGeneration(episodeId);
    },
    [runEpisodeGeneration],
  );

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

  const upgradeToStandard = useCallback(
    async (_episodeId: string, _variantsCount: number = 2): Promise<boolean> => {
      return false;
    },
    [],
  );

  const selectVariant = useCallback(
    (episodeId: string, variantIndex: number) => {
      const episode = episodes.find((item) => item.id === episodeId);
      if (!episode?.variants || variantIndex >= episode.variants.length) return;
      setEpisodes((prev) =>
        updateEpisodeById(prev, episodeId, {
          videoUrl: episode.variants![variantIndex],
          selectedVariantIndex: variantIndex,
        }),
      );
    },
    [episodes],
  );

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

  // ── Storyboard (Gemini Flash / Seedream 5.0) ──
  const regenerateFrame = useCallback(
    async (index: number) => {
      const episode = episodes[index];
      if (!episode) return;
      setError(null);
      setIsStoryboarding(true);
      try {
        const localRefs = referenceLocalUrls.filter((u) => u.trim());
        const resp = await regenerateStoryboardFrame({
          anchor_prompt: anchorPrompt || '',
          character_card: characterCard || '',
          episode_prompt: episode.prompt,
          aspect_ratio: ideaForm.aspectRatio,
          seed: storyboardSeed ?? undefined,
          image_model: imageModel,
          reference_image_urls: localRefs.length > 0 ? localRefs : undefined,
        });
        if (!resp.success || !resp.frame_url) {
          throw new Error(resp.error || 'Frame regeneration failed');
        }
        setStoryboardFrames((prev) => {
          const next = [...prev];
          while (next.length <= index) next.push('');
          next[index] = resp.frame_url!;
          return next;
        });
        // Drop any user override on this frame so the new keyframe is used
        setEpisodes((prev) =>
          prev.map((ep, i) => {
            if (i !== index || !ep.firstFrameUrl) return ep;
            const copy = { ...ep };
            delete copy.firstFrameUrl;
            return copy;
          }),
        );
        setNotice(t('generateV2.frameRegenerated', { count: index + 1 }));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Frame regeneration failed');
      } finally {
        setIsStoryboarding(false);
      }
    },
    [episodes, anchorPrompt, characterCard, ideaForm.aspectRatio, storyboardSeed, imageModel, referenceLocalUrls, t],
  );

  const setEpisodeFirstFrame = useCallback((episodeId: string, url: string | null) => {
    setEpisodes((prev) =>
      prev.map((ep) => {
        if (ep.id !== episodeId) return ep;
        if (url === null) {
          const copy = { ...ep };
          delete copy.firstFrameUrl;
          return copy;
        }
        return { ...ep, firstFrameUrl: url };
      }),
    );
  }, []);

  const runStoryboard = useCallback(async () => {
    if (episodes.length === 0) return;
    setIsStoryboarding(true);
    setError(null);
    try {
      const prompts = episodes.map((ep) => ep.prompt);
      // Use local URLs for storyboard (backend reads files from disk, not via HTTP)
      const localRefs = referenceLocalUrls.filter((url) => url.trim());
      const resp = await generateStoryboard({
        anchor_prompt: anchorPrompt || '',
        character_card: characterCard || '',
        episode_prompts: prompts,
        aspect_ratio: ideaForm.aspectRatio,
        seed: storyboardSeed ?? undefined,
        image_model: imageModel,
        reference_image_urls: localRefs.length > 0 ? localRefs : undefined,
      });
      if (!resp.success) throw new Error(resp.error || 'Storyboard failed');
      setStoryboardFrames(resp.keyframes);
      setStoryboardAudit(resp.audit || []);
      if (resp.seed) setStoryboardSeed(resp.seed);
      setNotice(t('generateV2.storyboardReady', { count: String(resp.keyframes.filter(Boolean).length) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Storyboard error');
    } finally {
      setIsStoryboarding(false);
    }
  }, [episodes, anchorPrompt, characterCard, ideaForm.aspectRatio, storyboardSeed, imageModel, referenceLocalUrls, t]);

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
    characterCard,
    voiceDescription,
    anchorPrompt,
    updateIdeaForm,
    updateEpisodeField,
    setEpisodeModel,
    applyModelToAll,
    dumpToTemplatePayload,
    applyTemplatePayload,
    goStep,
    resetFlow,
    planEpisodes,
    runQueue,
    retryEpisode,
    removeEpisode,
    moveEpisode,
    regenerateEpisode,
    selectPublishEpisode,
    updatePublishForm,
    upgradeToStandard,
    selectVariant,
    stitchEpisodes,
    publishToReview,
    runStoryboard,
    regenerateFrame,
    setEpisodeFirstFrame,
    isStoryboarding,
    storyboardFrames,
    storyboardAudit,
    imageModel,
    setImageModel,
    referenceImages,
    setReferenceImages,
    referenceLocalUrls,
    setReferenceLocalUrls,
  };
}
