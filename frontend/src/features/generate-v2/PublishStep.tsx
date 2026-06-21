import { Film, Loader2, Send } from 'lucide-react';
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Select } from '@/components/ui';
import { EpisodeDraft, PublishFormState } from './types';
import { useLanguage } from '@/contexts/LanguageContext';
import VoiceoverPanel from './VoiceoverPanel';
import MusicPanel from './MusicPanel';

interface PublishStepProps {
  episodes: EpisodeDraft[];
  form: PublishFormState;
  isPublishing: boolean;
  isStitching: boolean;
  stitchedVideoUrl: string | null;
  stitchedDuration: number | null;
  onSelectEpisode: (id: string) => void;
  onChange: <K extends keyof PublishFormState>(key: K, value: PublishFormState[K]) => void;
  onStitch: () => void;
  onPublish: () => void;
}

export default function PublishStep({
  episodes,
  form,
  isPublishing,
  isStitching,
  stitchedVideoUrl,
  stitchedDuration,
  onSelectEpisode,
  onChange,
  onStitch,
  onPublish,
}: PublishStepProps) {
  const { t } = useLanguage();
  const readyEpisodes = episodes.filter((episode) => episode.status === 'done' && episode.videoUrl);
  const canStitch = readyEpisodes.length > 1;
  const selectedEpisode = readyEpisodes.find((e) => e.id === form.selectedEpisodeId);
  const voiceoverTargetUrl: string | null =
    stitchedVideoUrl || selectedEpisode?.videoUrl || null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('generateV2.sendToReviewQueue')}</CardTitle>
        <CardDescription>{t('generateV2.sendToReviewDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Stitch section: show when multiple episodes ready and not yet stitched */}
        {canStitch && !stitchedVideoUrl && (
          <div className="space-y-2">
            <Button onClick={onStitch} disabled={isStitching} variant="secondary" className="w-full">
              {isStitching ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t('generateV2.stitching')}
                </>
              ) : (
                <>
                  <Film className="w-4 h-4" />
                  {t('generateV2.stitchAll')}
                </>
              )}
            </Button>
          </div>
        )}

        {/* Stitched video preview */}
        {stitchedVideoUrl && (
          <div className="space-y-2">
            <label className="text-sm text-green-400 font-medium">{t('generateV2.stitched')}</label>
            {stitchedDuration != null && (
              <p className="text-xs text-[var(--muted)]">
                {t('generateV2.stitchedDuration', { duration: String(Math.round(stitchedDuration)) })}
              </p>
            )}
            <video
              src={stitchedVideoUrl}
              controls
              className="w-full max-h-[400px] rounded-[var(--radius-sm)] bg-black"
            />
          </div>
        )}

        {/* Episode select: only show when no stitched video */}
        {!stitchedVideoUrl && (
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generateV2.generatedEpisode')}</label>
            <Select value={form.selectedEpisodeId} onChange={(event) => onSelectEpisode(event.target.value)}>
              <option value="">{t('generateV2.selectEpisode')}</option>
              {readyEpisodes.map((episode) => (
                <option key={episode.id} value={episode.id}>
                  {t('generateV2.episodeN', { count: episode.number })}: {episode.title}
                </option>
              ))}
            </Select>
          </div>
        )}

        {voiceoverTargetUrl && <VoiceoverPanel videoUrl={voiceoverTargetUrl} />}
        {voiceoverTargetUrl && <MusicPanel videoUrl={voiceoverTargetUrl} />}

        <div className="space-y-2">
          <label className="text-sm text-[var(--muted)]">{t('review.titleLabel')}</label>
          <Input value={form.title} onChange={(event) => onChange('title', event.target.value)} placeholder={t('generateV2.seoReadyTitle')} />
        </div>

        <div className="space-y-2">
          <label className="text-sm text-[var(--muted)]">{t('review.descriptionLabel')}</label>
          <textarea
            rows={4}
            value={form.description}
            onChange={(event) => onChange('description', event.target.value)}
            className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
            placeholder={t('generateV2.reviewerSummaryPlaceholder')}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm text-[var(--muted)]">{t('review.tagsLabel')}</label>
          <Input
            value={form.tagsCsv}
            onChange={(event) => onChange('tagsCsv', event.target.value)}
            placeholder={t('generateV2.tagsPlaceholder')}
          />
        </div>

        <Button onClick={onPublish} disabled={isPublishing || (!stitchedVideoUrl && !form.selectedEpisodeId)}>
          <Send className="w-4 h-4" />
          {isPublishing ? t('generate.sendingToReview') : t('generate.sendToReview')}
        </Button>
      </CardContent>
    </Card>
  );
}
