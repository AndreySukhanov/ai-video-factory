import { Loader2, RefreshCw, ArrowRight, Sparkles, X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui';
import ImageUploader, { UploadedImage } from './ImageUploader';
import { EpisodeDraft } from './types';
import { ImageModel, FrameAuditReport } from '@/lib/api/generation';
import { useLanguage } from '@/contexts/LanguageContext';

interface StoryboardStepProps {
  episodes: EpisodeDraft[];
  storyboardFrames: string[];
  storyboardAudit?: FrameAuditReport[];
  imageModel: ImageModel;
  isStoryboarding: boolean;
  onImageModelChange: (model: ImageModel) => void;
  onRunStoryboard: () => void;
  onRegenerateFrame: (index: number) => void;
  onSetEpisodeFirstFrame: (episodeId: string, url: string | null) => void;
  onContinue: () => void;
}

function scoreColor(score: number): string {
  if (score >= 90) return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
  if (score >= 70) return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  return 'bg-red-500/20 text-red-300 border-red-500/40';
}

export default function StoryboardStep({
  episodes,
  storyboardFrames,
  storyboardAudit,
  imageModel,
  isStoryboarding,
  onImageModelChange,
  onRunStoryboard,
  onRegenerateFrame,
  onSetEpisodeFirstFrame,
  onContinue,
}: StoryboardStepProps) {
  const { t } = useLanguage();
  const hasAnyFrame = storyboardFrames.some((f) => !!f);
  const auditByIndex = new Map<number, FrameAuditReport>();
  (storyboardAudit || []).forEach((a) => auditByIndex.set(a.index, a));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('generateV2.stepStoryboardLabel')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-[var(--muted)]">
            {t('generateV2.stepStoryboardHint')}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <label className="text-xs text-[var(--muted)] block mb-1">
                {t('generateV2.imageModel')}
              </label>
              <select
                value={imageModel}
                disabled={isStoryboarding}
                onChange={(e) => onImageModelChange(e.target.value as ImageModel)}
                className="text-sm bg-black/30 border border-white/10 rounded px-2 py-1.5 text-white focus:outline-none focus:border-purple-500"
              >
                <option value="gemini">Gemini Nano Banana</option>
                <option value="seedream">Seedream 5.0</option>
                <option value="flux">FLUX Schnell</option>
              </select>
            </div>
            <Button
              onClick={onRunStoryboard}
              disabled={isStoryboarding || episodes.length === 0}
            >
              {isStoryboarding ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Sparkles className="w-4 h-4" />
              )}
              {hasAnyFrame
                ? t('generateV2.regenerateAllFrames')
                : t('generateV2.generateStoryboard')}
            </Button>
            <Button variant="secondary" onClick={onContinue}>
              {hasAnyFrame
                ? t('generateV2.continueToGeneration')
                : t('generateV2.skipStoryboard')}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {episodes.map((episode, idx) => {
          const generatedUrl = storyboardFrames[idx] || '';
          const overrideUrl = episode.firstFrameUrl || '';
          const displayUrl = overrideUrl || generatedUrl;
          const hasOverride = !!overrideUrl;

          const audit = auditByIndex.get(idx);
          return (
            <Card key={episode.id}>
              <CardContent className="p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">
                    {t('generateV2.episodeN', { count: episode.number })}
                  </span>
                  <div className="flex items-center gap-1">
                    {audit && !hasOverride && (
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border ${scoreColor(audit.score)} flex items-center gap-1`}
                        title={audit.mismatches.length > 0 ? audit.mismatches.join('; ') : t('generateV2.auditPerfect')}
                      >
                        {audit.score >= 90 ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                        {audit.score}/100
                      </span>
                    )}
                    {audit?.regenerated && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded border bg-purple-500/20 text-purple-300 border-purple-500/40">
                        {t('generateV2.auditRegenerated')}
                      </span>
                    )}
                    {hasOverride && (
                      <span className="text-[10px] text-amber-400 uppercase tracking-wide">
                        {t('generateV2.userOverride')}
                      </span>
                    )}
                  </div>
                </div>

                <div className="aspect-[9/14] bg-black/40 rounded-lg overflow-hidden border border-white/10 relative flex items-center justify-center">
                  {displayUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={displayUrl}
                      alt={`Frame ${episode.number}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="text-xs text-[var(--muted)] text-center px-2">
                      {t('generateV2.frameEmpty')}
                    </div>
                  )}
                </div>

                {audit && !hasOverride && audit.mismatches.length > 0 && (
                  <div className="text-[11px] text-amber-300/80 leading-tight">
                    {audit.mismatches.slice(0, 2).map((m, i) => (
                      <div key={i} className="truncate" title={m}>• {m}</div>
                    ))}
                  </div>
                )}

                <div className="text-xs text-[var(--muted)] line-clamp-2">
                  {episode.title}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onRegenerateFrame(idx)}
                    disabled={isStoryboarding}
                    title={t('generateV2.regenerateFrame')}
                  >
                    <RefreshCw className="w-3 h-3" />
                    {t('generateV2.regenerateFrame')}
                  </Button>
                  {hasOverride && (
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onSetEpisodeFirstFrame(episode.id, null)}
                      disabled={isStoryboarding}
                      title={t('generateV2.removeOverride')}
                    >
                      <X className="w-3 h-3" />
                      {t('generateV2.removeOverride')}
                    </Button>
                  )}
                </div>

                <div className="pt-1 border-t border-white/5">
                  <ImageUploader
                    label={t('generateV2.uploadCustomFrame')}
                    currentUrl={overrideUrl || undefined}
                    onUploaded={(img: UploadedImage) =>
                      onSetEpisodeFirstFrame(episode.id, img.localUrl || img.url)
                    }
                    onRemove={() => onSetEpisodeFirstFrame(episode.id, null)}
                  />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
