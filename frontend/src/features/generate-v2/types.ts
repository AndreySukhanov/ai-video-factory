import { GenerationModel } from '@/lib/api/generation';

export type FlowStepId = 'idea' | 'episodes' | 'generation' | 'publish';

export interface FlowStep {
  id: FlowStepId;
  label: string;
  hint: string;
}

export interface IdeaFormState {
  idea: string;
  genre: string;
  episodesCount: number;
  duration: number;
  aspectRatio: string;
  model: GenerationModel;
}

export type EpisodeStatus = 'queued' | 'generating' | 'done' | 'error';

export interface EpisodeDraft {
  id: string;
  number: number;
  title: string;
  synopsis: string;
  prompt: string;
  status: EpisodeStatus;
  videoUrl?: string;
  error?: string;
  anchorPrompt?: string;       // shared across all episodes
  variablePrompt?: string;     // unique per episode
  previewUrl?: string;         // fast preview URL (Phase 2)
  variants?: string[];         // multiple variant URLs (Phase 2)
  selectedVariantIndex?: number;
  qualityMode?: 'fast' | 'standard';
  firstFrameUrl?: string;      // first frame image for transition
  lastFrameUrl?: string;       // last frame image for transition
  model?: GenerationModel;     // override video model for this episode (falls back to ideaForm.model)
  duration?: number;           // override duration for this episode (falls back to ideaForm.duration)
}

export interface PublishFormState {
  selectedEpisodeId: string;
  title: string;
  description: string;
  tagsCsv: string;
}

export interface GenerationDraftSnapshot {
  ideaForm: IdeaFormState;
  episodes: EpisodeDraft[];
  seriesTitle: string;
  seriesLogline: string;
  currentStep: FlowStepId;
  characterCard?: string;
  voiceDescription?: string;
  anchorPrompt?: string;
  storyboardFrames?: string[];
  referenceImages?: string[];
}
