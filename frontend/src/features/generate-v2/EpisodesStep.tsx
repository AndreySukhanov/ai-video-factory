import { useState } from 'react';
import { ChevronDown, ChevronRight, ImageIcon, Play } from 'lucide-react';
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Select } from '@/components/ui';
import { EpisodeDraft, IdeaFormState } from './types';
import { GenerationModel, ImageModel } from '@/lib/api/generation';
import { useLanguage } from '@/contexts/LanguageContext';
import ImageUploader, { UploadedImage } from './ImageUploader';

interface EpisodesStepProps {
  seriesTitle: string;
  seriesLogline: string;
  ideaForm: IdeaFormState;
  episodes: EpisodeDraft[];
  onIdeaChange: <K extends keyof IdeaFormState>(key: K, value: IdeaFormState[K]) => void;
  onEpisodeChange: <K extends keyof EpisodeDraft>(id: string, key: K, value: EpisodeDraft[K]) => void;
  onRunGeneration: () => void;
  onRunStoryboard?: () => void;
  isStoryboarding?: boolean;
  storyboardFrames?: string[];
  imageModel?: ImageModel;
  onImageModelChange?: (model: ImageModel) => void;
  referenceImages: string[];
  onReferenceImagesChange: (images: string[]) => void;
  referenceLocalUrls: string[];
  onReferenceLocalUrlsChange: (urls: string[]) => void;
}

const SINGLE_MODEL_KEYS = [
  { value: 'seedance', i18nKey: 'generateV2.videoModelSeedance' },
  { value: 'laozhang', i18nKey: 'generateV2.videoModelLaozhang' },
  { value: 'vertex', i18nKey: 'generateV2.videoModelVertex' },
  { value: 'kling', i18nKey: 'generateV2.videoModelKling' },
] as const;

const SERIES_MODEL_KEYS = [
  { value: 'seedance', i18nKey: 'generateV2.videoModelSeedanceSeries' },
  { value: 'laozhang', i18nKey: 'generateV2.videoModelLaozhang' },
  { value: 'vertex', i18nKey: 'generateV2.videoModelVertex' },
  { value: 'minimax', i18nKey: 'generateV2.videoModelMinimax' },
] as const;

const MODEL_DURATION_OPTIONS: Record<IdeaFormState['model'], readonly number[]> = {
  kling: [5, 10],
  minimax: [6],
  laozhang: [4, 6, 8],
  gemini: [4, 6, 8],
  vertex: [4, 6, 8],
  seedance: [4, 5, 8, 10, 15],
};

const MODELS_WITH_REFS: GenerationModel[] = ['vertex', 'laozhang', 'seedance'];
const MODELS_WITH_TRANSITION: GenerationModel[] = ['vertex', 'laozhang'];

function estimatePerEpisodeCost(model: GenerationModel, duration: number): number {
  switch (model) {
    case 'seedance': return 0.05;
    case 'laozhang': return 0.15;
    case 'vertex': return duration * 0.15;
    case 'kling': return duration <= 5 ? 0.25 : 0.50;
    case 'minimax': return 0.50;
    case 'gemini': return duration * 0.15;
  }
}

export default function EpisodesStep({
  seriesTitle,
  seriesLogline,
  ideaForm,
  episodes,
  onIdeaChange,
  onEpisodeChange,
  onRunGeneration,
  onRunStoryboard,
  isStoryboarding,
  storyboardFrames = [],
  imageModel = 'gemini',
  onImageModelChange,
  referenceImages,
  onReferenceImagesChange,
  referenceLocalUrls,
  onReferenceLocalUrlsChange,
}: EpisodesStepProps) {
  const { t } = useLanguage();
  const [expandedFrameControl, setExpandedFrameControl] = useState<Record<string, boolean>>({});
  const isSeriesMode = ideaForm.episodesCount > 1;
  const visibleModelKeys = isSeriesMode ? SERIES_MODEL_KEYS : SINGLE_MODEL_KEYS;
  const modelHintKey = isSeriesMode ? 'generateV2.seriesModelsHint' : 'generateV2.singleModelsHint';
  const durationOptions = MODEL_DURATION_OPTIONS[ideaForm.model];
  const totalDurationSec = ideaForm.duration * ideaForm.episodesCount;

  const supportsRefs = MODELS_WITH_REFS.includes(ideaForm.model);
  const supportsTransition = MODELS_WITH_TRANSITION.includes(ideaForm.model);

  const perEpisodeCost = estimatePerEpisodeCost(ideaForm.model, ideaForm.duration);
  const totalCost = perEpisodeCost * ideaForm.episodesCount;

  const statusLabel = (status: EpisodeDraft['status']) => {
    if (status === 'done') return t('generateV2.statusDone');
    if (status === 'error') return t('generateV2.statusFailed');
    if (status === 'generating') return t('generateV2.statusRunning');
    return t('generateV2.statusQueued');
  };

  const setRefImage = (index: number, img: UploadedImage) => {
    const nextUrls = [...referenceImages];
    nextUrls[index] = img.url;
    onReferenceImagesChange(nextUrls);
    const nextLocal = [...referenceLocalUrls];
    nextLocal[index] = img.localUrl;
    onReferenceLocalUrlsChange(nextLocal);
  };

  const removeRefImage = (index: number) => {
    onReferenceImagesChange(referenceImages.filter((_, i) => i !== index));
    onReferenceLocalUrlsChange(referenceLocalUrls.filter((_, i) => i !== index));
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
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
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
                {visibleModelKeys.map((model) => (
                  <option key={model.value} value={model.value}>
                    {t(model.i18nKey)}
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
          </div>

          {/* Reference Photos (file upload) */}
          {supportsRefs && (
            <div className="space-y-2 border-t border-white/10 pt-3">
              <label className="text-sm text-[var(--muted)]">{t('generateV2.referencePhotos')}</label>
              <p className="text-xs text-[var(--muted)]">{t('generateV2.referencePhotosHint')}</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <ImageUploader
                  label={t('generateV2.uploadCharacterPhoto')}
                  currentUrl={referenceImages[0] || undefined}
                  onUploaded={(img) => setRefImage(0, img)}
                  onRemove={() => removeRefImage(0)}
                />
                <ImageUploader
                  label={t('generateV2.uploadLocationPhoto')}
                  currentUrl={referenceImages[1] || undefined}
                  onUploaded={(img) => setRefImage(1, img)}
                  onRemove={() => removeRefImage(1)}
                />
              </div>
            </div>
          )}
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
            {storyboardFrames[episode.number - 1] && (
              <div className="space-y-1">
                <label className="text-xs text-[var(--muted)]">{t('generateV2.storyboard')}</label>
                <img
                  src={storyboardFrames[episode.number - 1]}
                  alt={`Keyframe ${episode.number}`}
                  className="w-full max-w-[200px] rounded-lg border border-white/10"
                />
              </div>
            )}

            {/* First / Last Frame upload (file only) */}
            {supportsTransition && (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setExpandedFrameControl((prev) => ({ ...prev, [episode.id]: !prev[episode.id] }))}
                  className="flex items-center gap-1 text-xs text-[var(--muted)] hover:text-white transition-colors"
                >
                  {expandedFrameControl[episode.id] ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                  {t('generateV2.frameControl')}
                </button>
                {expandedFrameControl[episode.id] && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-3">
                      <ImageUploader
                        label={t('generateV2.firstFrameUrl')}
                        currentUrl={episode.firstFrameUrl || undefined}
                        onUploaded={(img) => onEpisodeChange(episode.id, 'firstFrameUrl', img.url)}
                        onRemove={() => onEpisodeChange(episode.id, 'firstFrameUrl', '')}
                      />
                      <ImageUploader
                        label={t('generateV2.lastFrameUrl')}
                        currentUrl={episode.lastFrameUrl || undefined}
                        onUploaded={(img) => onEpisodeChange(episode.id, 'lastFrameUrl', img.url)}
                        onRemove={() => onEpisodeChange(episode.id, 'lastFrameUrl', '')}
                      />
                    </div>
                    <p className="text-xs text-[var(--muted)]">{t('generateV2.transitionHint')}</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}

      <div className="flex flex-wrap items-center gap-3">
        {onRunStoryboard && supportsRefs && referenceImages.some((url) => url.trim()) && (
          <>
            <Select
              value={imageModel}
              onChange={(event) => onImageModelChange?.(event.target.value as ImageModel)}
              className="w-auto"
            >
              <option value="gemini">{t('generateV2.imageModelGemini')}</option>
              <option value="flux">{t('generateV2.imageModelFlux')}</option>
              <option value="seedream">{t('generateV2.imageModelSeedream')}</option>
            </Select>
            <Button onClick={onRunStoryboard} variant="secondary" disabled={isStoryboarding}>
              <ImageIcon className="w-4 h-4" />
              {isStoryboarding ? t('generateV2.storyboardGenerating') : t('generateV2.aiStoryboardFromPhoto')}
            </Button>
          </>
        )}
        <Button onClick={onRunGeneration} className="w-full md:w-auto">
          <Play className="w-4 h-4" />
          {t('generateV2.startGenerationQueue')}
        </Button>
        <span className="text-sm text-[var(--muted)]">
          {t('generateV2.estimatedCost', { cost: totalCost.toFixed(2) })}
          {' '}({t('generateV2.costPerEpisode', { cost: perEpisodeCost.toFixed(2) })})
        </span>
      </div>
    </div>
  );
}
