import { Loader2, RefreshCw, Video, ChevronUp, ChevronDown, RotateCcw } from 'lucide-react';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, ProgressBar } from '@/components/ui';
import { EpisodeDraft } from './types';
import { GenerationModel } from '@/lib/api/generation';
import { useLanguage } from '@/contexts/LanguageContext';

const SINGLE_EPISODE_MODELS: GenerationModel[] = ['seedance', 'wavespeed', 'wavespeed-standard', 'wavespeed-v15', 'laozhang', 'vertex', 'kling'];
const SERIES_MODELS: GenerationModel[] = ['seedance', 'wavespeed', 'wavespeed-standard', 'wavespeed-v15', 'laozhang', 'vertex', 'minimax'];

const MODEL_LABELS: Record<GenerationModel, string> = {
  seedance: 'Seedance 2.0 (LaoZhang)',
  wavespeed: 'Seedance 2.0 Fast (WaveSpeed)',
  'wavespeed-standard': 'Seedance 2.0 Standard (WaveSpeed)',
  'wavespeed-v15': 'Seedance v1.5-pro (WaveSpeed)',
  laozhang: 'Veo 3.1 (LaoZhang)',
  vertex: 'Veo 3.1 (Vertex)',
  gemini: 'Veo 3.1 (Gemini)',
  kling: 'Kling 2.6 (Replicate)',
  minimax: 'MiniMax S2V (Replicate)',
  fal: 'Pika (fal.ai)',
};

interface GenerationStepProps {
  episodes: EpisodeDraft[];
  isGenerating: boolean;
  onRunQueue: () => void;
  onRetryEpisode: (id: string) => void;
  onMoveEpisode?: (id: string, direction: 'up' | 'down') => void;
  onRegenerateEpisode?: (id: string) => void;
  defaultModel: GenerationModel;
  episodesCount: number;
  onSetEpisodeModel?: (id: string, model: GenerationModel | null) => void;
  onApplyModelToAll?: (model: GenerationModel) => void;
}

function statusBadgeVariant(status: EpisodeDraft['status']): 'muted' | 'success' | 'danger' | 'warning' {
  if (status === 'done') return 'success';
  if (status === 'error') return 'danger';
  if (status === 'generating') return 'warning';
  return 'muted';
}

export default function GenerationStep({
  episodes,
  isGenerating,
  onRunQueue,
  onRetryEpisode,
  onMoveEpisode,
  onRegenerateEpisode,
  defaultModel,
  episodesCount,
  onSetEpisodeModel,
  onApplyModelToAll,
}: GenerationStepProps) {
  const { t } = useLanguage();
  const completed = episodes.filter((episode) => episode.status === 'done').length;
  const progress = episodes.length ? (completed / episodes.length) * 100 : 0;
  const allowedModels = episodesCount > 1 ? SERIES_MODELS : SINGLE_EPISODE_MODELS;

  const statusLabel = (status: EpisodeDraft['status']) => {
    if (status === 'done') return t('generateV2.statusDone');
    if (status === 'error') return t('generateV2.statusFailed');
    if (status === 'generating') return t('generateV2.statusRunning');
    return t('generateV2.statusQueued');
  };

  const hasOverride = episodes.some((ep) => ep.model && ep.model !== defaultModel);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('generateV2.generationQueue')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ProgressBar value={progress} showValue />
          <div className="text-sm text-[var(--muted)]">
            {t('generateV2.completedOf', { completed, total: episodes.length })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={onRunQueue} disabled={isGenerating || episodes.length === 0}>
              {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Video className="w-4 h-4" />}
              {isGenerating ? t('generate.generating') : t('generateV2.runQueue')}
            </Button>
            {onApplyModelToAll && hasOverride && (
              <Button
                size="sm"
                variant="secondary"
                disabled={isGenerating}
                onClick={() => onApplyModelToAll(defaultModel)}
                title={t('generateV2.resetAllToDefault')}
              >
                <RotateCcw className="w-3 h-3" />
                {t('generateV2.resetAllToDefault')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {episodes.map((episode, idx) => {
          const effectiveModel = (episode.model ?? defaultModel) as GenerationModel;
          const isOverride = !!episode.model && episode.model !== defaultModel;
          return (
            <Card key={episode.id}>
              <CardContent className="p-4">
                <div className="flex flex-col md:flex-row gap-4">
                  {/* Reorder arrows */}
                  {onMoveEpisode && (
                    <div className="flex md:flex-col items-center justify-center gap-0.5">
                      <button
                        type="button"
                        onClick={() => onMoveEpisode(episode.id, 'up')}
                        disabled={idx === 0 || isGenerating}
                        className="text-white/40 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed p-1 rounded hover:bg-white/10 transition-colors"
                        title={t('generateV2.moveUp')}
                      >
                        <ChevronUp className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onMoveEpisode(episode.id, 'down')}
                        disabled={idx === episodes.length - 1 || isGenerating}
                        className="text-white/40 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed p-1 rounded hover:bg-white/10 transition-colors"
                        title={t('generateV2.moveDown')}
                      >
                        <ChevronDown className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{t('generateV2.episodeN', { count: episode.number })}</span>
                      <Badge variant={statusBadgeVariant(episode.status)}>{statusLabel(episode.status)}</Badge>
                    </div>
                    <div className="text-sm text-[var(--muted)]">{episode.title}</div>

                    {/* Per-episode model selector */}
                    {onSetEpisodeModel && (
                      <div className="mt-2 flex items-center gap-2">
                        <label className="text-xs text-[var(--muted)] shrink-0">
                          {t('generateV2.episodeModel')}
                        </label>
                        <select
                          value={effectiveModel}
                          disabled={isGenerating || episode.status === 'generating'}
                          onChange={(e) => {
                            const next = e.target.value as GenerationModel;
                            onSetEpisodeModel(episode.id, next === defaultModel ? null : next);
                          }}
                          className="text-xs bg-black/30 border border-white/10 rounded px-2 py-1 text-white focus:outline-none focus:border-purple-500"
                        >
                          {allowedModels.map((m) => (
                            <option key={m} value={m} className="bg-gray-800">
                              {MODEL_LABELS[m]}
                              {m === defaultModel ? ` (${t('generateV2.useDefault')})` : ''}
                            </option>
                          ))}
                        </select>
                        {isOverride && (
                          <button
                            type="button"
                            onClick={() => onSetEpisodeModel(episode.id, null)}
                            disabled={isGenerating}
                            className="text-xs text-purple-400 hover:text-purple-300 disabled:opacity-50"
                            title={t('generateV2.useDefault')}
                          >
                            {t('generateV2.useDefault')}
                          </button>
                        )}
                      </div>
                    )}

                    {episode.error && (
                      <div className="text-xs text-red-400 mt-1">
                        {episode.error}
                        {(episode.error.includes('503') || episode.error.includes('Service Unavailable')) && (
                          <span className="block mt-1 text-amber-400">⚠ Модель временно недоступна — выберите Kling 2.1 в настройках выше.</span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="w-full md:w-56">
                    {episode.videoUrl ? (
                      <video src={episode.videoUrl} controls className="w-full rounded-lg bg-black" preload="metadata" />
                    ) : (
                      <div className="h-32 rounded-lg border border-dashed border-white/15 bg-white/5 flex items-center justify-center text-xs text-[var(--muted)]">
                        {t('generateV2.noClipYet')}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-3 flex gap-2">
                  {episode.status === 'error' && (
                    <Button size="sm" variant="secondary" onClick={() => onRetryEpisode(episode.id)}>
                      <RefreshCw className="w-3 h-3" />
                      {t('generateV2.retry')}
                    </Button>
                  )}
                  {onRegenerateEpisode && episode.status === 'done' && (
                    <Button size="sm" variant="secondary" onClick={() => onRegenerateEpisode(episode.id)} disabled={isGenerating}>
                      <RotateCcw className="w-3 h-3" />
                      {t('generateV2.regenerate')}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
