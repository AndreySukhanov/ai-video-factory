import { Clock3, RefreshCw, AlertTriangle, Trash2, ChevronUp, ChevronDown, RotateCcw } from 'lucide-react';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, ProgressBar } from '@/components/ui';
import { EpisodeDraft, FlowStepId } from './types';
import { useLanguage } from '@/contexts/LanguageContext';

interface StatusPanelProps {
  currentStep: FlowStepId;
  episodes: EpisodeDraft[];
  isGenerating: boolean;
  onRetryEpisode: (id: string) => void;
  onDeleteEpisode: (id: string) => void;
  onMoveEpisode?: (id: string, direction: 'up' | 'down') => void;
  onRegenerateEpisode?: (id: string) => void;
}

export default function StatusPanel({ currentStep, episodes, isGenerating, onRetryEpisode, onDeleteEpisode, onMoveEpisode, onRegenerateEpisode }: StatusPanelProps) {
  const { t } = useLanguage();
  const done = episodes.filter((episode) => episode.status === 'done').length;
  const failed = episodes.filter((episode) => episode.status === 'error').length;
  const processing = episodes.filter((episode) => episode.status === 'generating').length;
  const total = episodes.length;
  const progress = total ? (done / total) * 100 : 0;
  const stepLabel = (step: FlowStepId): string => {
    if (step === 'idea') return t('generateV2.stepIdeaLabel');
    if (step === 'episodes') return t('generateV2.stepEpisodesLabel');
    if (step === 'generation') return t('generateV2.stepGenerationLabel');
    return t('generateV2.stepPublishLabel');
  };

  const statusLabel = (status: EpisodeDraft['status']) => {
    if (status === 'done') return t('generateV2.statusDone');
    if (status === 'error') return t('generateV2.statusFailed');
    if (status === 'generating') return t('generateV2.statusRunning');
    return t('generateV2.statusQueued');
  };

  return (
    <div className="space-y-4 lg:sticky lg:top-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock3 className="w-4 h-4 text-[var(--brand-2)]" />
            {t('generateV2.pipelineStatus')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-sm text-[var(--muted)]">{t('generateV2.currentStep', { step: stepLabel(currentStep) })}</div>
          <ProgressBar value={progress} showValue />
          <div className="flex flex-wrap gap-2">
            <Badge variant="success">{t('generateV2.doneN', { count: done })}</Badge>
            <Badge variant="warning">{t('generateV2.runningN', { count: processing })}</Badge>
            <Badge variant="danger">{t('generateV2.failedN', { count: failed })}</Badge>
          </div>
          {isGenerating && <div className="text-xs text-[var(--brand-2)]">{t('generateV2.queueRunning')}</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('generateV2.episodeQueue')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 max-h-[55vh] overflow-auto">
          {episodes.length === 0 && <div className="text-sm text-[var(--muted)]">{t('generateV2.noEpisodesYet')}</div>}
          {episodes.map((episode, idx) => (
            <div key={episode.id} className="rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-2)]/60 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  {onMoveEpisode && (
                    <div className="flex flex-col -my-1">
                      <button
                        type="button"
                        onClick={() => onMoveEpisode(episode.id, 'up')}
                        disabled={idx === 0 || isGenerating}
                        className="text-white/40 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed p-0.5"
                        title={t('generateV2.moveUp')}
                      >
                        <ChevronUp className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onMoveEpisode(episode.id, 'down')}
                        disabled={idx === episodes.length - 1 || isGenerating}
                        className="text-white/40 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed p-0.5"
                        title={t('generateV2.moveDown')}
                      >
                        <ChevronDown className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                  <div className="text-xs font-medium">E{episode.number}: {episode.title || t('review.untitled')}</div>
                </div>
                <div className="flex items-center gap-1">
                  <Badge variant={episode.status === 'done' ? 'success' : episode.status === 'error' ? 'danger' : 'muted'}>
                    {statusLabel(episode.status)}
                  </Badge>
                  {onRegenerateEpisode && episode.status === 'done' && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onRegenerateEpisode(episode.id)}
                      disabled={isGenerating}
                      aria-label={t('generateV2.regenerate')}
                      title={t('generateV2.regenerate')}
                    >
                      <RotateCcw className="w-3 h-3" />
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onDeleteEpisode(episode.id)}
                    disabled={isGenerating || episode.status === 'generating'}
                    aria-label={t('generateV2.deleteEpisode')}
                    title={t('generateV2.deleteEpisode')}
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </div>
              {episode.status === 'error' && (
                <div className="mt-2">
                  <div className="text-xs text-red-300 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {episode.error || t('generateV2.statusFailed')}
                  </div>
                  <Button size="sm" variant="secondary" className="mt-2" onClick={() => onRetryEpisode(episode.id)}>
                    <RefreshCw className="w-3 h-3" />
                    {t('generateV2.retry')}
                  </Button>
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
