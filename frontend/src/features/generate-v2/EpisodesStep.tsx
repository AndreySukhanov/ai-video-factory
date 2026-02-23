import { Play } from 'lucide-react';
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Select } from '@/components/ui';
import { EpisodeDraft, IdeaFormState } from './types';
import { useLanguage } from '@/contexts/LanguageContext';

interface EpisodesStepProps {
  seriesTitle: string;
  seriesLogline: string;
  ideaForm: IdeaFormState;
  episodes: EpisodeDraft[];
  onIdeaChange: <K extends keyof IdeaFormState>(key: K, value: IdeaFormState[K]) => void;
  onEpisodeChange: <K extends keyof EpisodeDraft>(id: string, key: K, value: EpisodeDraft[K]) => void;
  onRunGeneration: () => void;
}

const SINGLE_MODEL_OPTIONS = [
  { value: 'veo3', label: 'Veo 3 Fast' },
  { value: 'kling', label: 'Kling 2.6' },
] as const;

const SERIES_MODEL_OPTIONS = [
  { value: 'minimax', label: 'MiniMax (S2V)' },
  { value: 'veo31', label: 'Veo 3.1 (R2V)' },
] as const;

const MODEL_DURATION_OPTIONS: Record<IdeaFormState['model'], readonly number[]> = {
  veo3: [4, 6, 8],
  veo31: [4, 6, 8],
  kling: [5, 10],
  minimax: [6],
};

export default function EpisodesStep({
  seriesTitle,
  seriesLogline,
  ideaForm,
  episodes,
  onIdeaChange,
  onEpisodeChange,
  onRunGeneration,
}: EpisodesStepProps) {
  const { t } = useLanguage();
  const isSeriesMode = ideaForm.episodesCount > 1;
  const visibleModelOptions = isSeriesMode ? SERIES_MODEL_OPTIONS : SINGLE_MODEL_OPTIONS;
  const modelHintKey = isSeriesMode ? 'generateV2.seriesModelsHint' : 'generateV2.singleModelsHint';
  const durationOptions = MODEL_DURATION_OPTIONS[ideaForm.model];
  const totalDurationSec = ideaForm.duration * ideaForm.episodesCount;

  const statusLabel = (status: EpisodeDraft['status']) => {
    if (status === 'done') return t('generateV2.statusDone');
    if (status === 'error') return t('generateV2.statusFailed');
    if (status === 'generating') return t('generateV2.statusRunning');
    return t('generateV2.statusQueued');
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{seriesTitle || t('generateV2.seriesDraft')}</CardTitle>
          <CardDescription>{seriesLogline || t('generateV2.reviewPromptsHint')}</CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('generate.settings')}</CardTitle>
          <CardDescription>{t('generateV2.reviewPromptsHint')}</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generate.aspectRatio')}</label>
            <Select value={ideaForm.aspectRatio} onChange={(event) => onIdeaChange('aspectRatio', event.target.value)}>
              <option value="9:16">9:16</option>
              <option value="16:9">16:9</option>
              <option value="1:1">1:1</option>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generate.aiModel')}</label>
            <Select value={ideaForm.model} onChange={(event) => onIdeaChange('model', event.target.value as IdeaFormState['model'])}>
              {visibleModelOptions.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </Select>
            <p className="text-xs text-[var(--muted)]">{t(modelHintKey)}</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generateV2.durationSec')}</label>
            <Select value={String(ideaForm.duration)} onChange={(event) => onIdeaChange('duration', Number(event.target.value))}>
              {durationOptions.map((duration) => (
                <option key={duration} value={duration}>
                  {t('generate.seconds', { count: duration })}
                </option>
              ))}
            </Select>
            <p className="text-xs text-[var(--muted)]">{t('generateV2.totalDurationEstimate', { count: totalDurationSec })}</p>
            {ideaForm.model === 'minimax' && (
              <p className="text-xs text-[var(--muted)]">{t('generateV2.minimaxDurationNote')}</p>
            )}
          </div>
        </CardContent>
      </Card>

      {episodes.map((episode) => (
        <Card key={episode.id}>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base">{t('generateV2.episodeN', { count: episode.number })}</CardTitle>
              <Badge variant="muted">{statusLabel(episode.status)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('review.titleLabel')}</label>
              <input
                value={episode.title}
                onChange={(event) => onEpisodeChange(episode.id, 'title', event.target.value)}
                className="h-10 w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] px-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.synopsis')}</label>
              <textarea
                rows={2}
                value={episode.synopsis}
                onChange={(event) => onEpisodeChange(episode.id, 'synopsis', event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generate.prompt')}</label>
              <textarea
                rows={4}
                value={episode.prompt}
                onChange={(event) => onEpisodeChange(episode.id, 'prompt', event.target.value)}
                className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
              />
            </div>
          </CardContent>
        </Card>
      ))}

      <Button onClick={onRunGeneration} className="w-full md:w-auto">
        <Play className="w-4 h-4" />
        {t('generateV2.startGenerationQueue')}
      </Button>
    </div>
  );
}
