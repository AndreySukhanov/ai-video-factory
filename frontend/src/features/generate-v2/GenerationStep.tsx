import { Loader2, RefreshCw, Video } from 'lucide-react';
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, ProgressBar } from '@/components/ui';
import { EpisodeDraft } from './types';
import { useLanguage } from '@/contexts/LanguageContext';

interface GenerationStepProps {
  episodes: EpisodeDraft[];
  isGenerating: boolean;
  onRunQueue: () => void;
  onRetryEpisode: (id: string) => void;
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
}: GenerationStepProps) {
  const { t } = useLanguage();
  const completed = episodes.filter((episode) => episode.status === 'done').length;
  const progress = episodes.length ? (completed / episodes.length) * 100 : 0;
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
          <CardTitle>{t('generateV2.generationQueue')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ProgressBar value={progress} showValue />
          <div className="text-sm text-[var(--muted)]">
            {t('generateV2.completedOf', { completed, total: episodes.length })}
          </div>
          <Button onClick={onRunQueue} disabled={isGenerating || episodes.length === 0}>
            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Video className="w-4 h-4" />}
            {isGenerating ? t('generate.generating') : t('generateV2.runQueue')}
          </Button>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {episodes.map((episode) => (
          <Card key={episode.id}>
            <CardContent className="p-4">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm">{t('generateV2.episodeN', { count: episode.number })}</span>
                    <Badge variant={statusBadgeVariant(episode.status)}>{statusLabel(episode.status)}</Badge>
                  </div>
                  <div className="text-sm text-[var(--muted)]">{episode.title}</div>
                  {episode.error && <div className="text-xs text-red-400 mt-1">{episode.error}</div>}
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
              {episode.status === 'error' && (
                <div className="mt-3">
                  <Button size="sm" variant="secondary" onClick={() => onRetryEpisode(episode.id)}>
                    <RefreshCw className="w-3 h-3" />
                    {t('generateV2.retry')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
