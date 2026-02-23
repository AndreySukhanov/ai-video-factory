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
}
