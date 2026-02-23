import { Loader2, Sparkles } from 'lucide-react';
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Select } from '@/components/ui';
import { IdeaFormState } from './types';
import { useLanguage } from '@/contexts/LanguageContext';

interface IdeaStepProps {
  value: IdeaFormState;
  isPlanning: boolean;
  onChange: <K extends keyof IdeaFormState>(key: K, value: IdeaFormState[K]) => void;
  onGenerate: () => void;
}

const GENRE_OPTIONS = [
  { value: 'drama', labelKey: 'generate.genreDrama' },
  { value: 'thriller', labelKey: 'generate.genreThriller' },
  { value: 'comedy', labelKey: 'generate.genreComedy' },
  { value: 'romance', labelKey: 'generate.genreRomance' },
  { value: 'mystery', labelKey: 'generate.genreMystery' },
  { value: 'scifi', labelKey: 'generate.genreSciFi' },
  { value: 'action', labelKey: 'generate.genreAction' },
] as const;

export default function IdeaStep({ value, isPlanning, onChange, onGenerate }: IdeaStepProps) {
  const { t } = useLanguage();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('generateV2.storySetupTitle')}</CardTitle>
        <CardDescription>{t('generateV2.storySetupDescription')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm text-[var(--muted)]">{t('generateV2.coreIdea')}</label>
          <textarea
            value={value.idea}
            onChange={(event) => onChange('idea', event.target.value)}
            rows={5}
            className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-3 text-sm text-white placeholder:text-[var(--muted)]/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
            placeholder={t('generateV2.coreIdeaPlaceholder')}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generate.genre')}</label>
            <Select value={value.genre} onChange={(event) => onChange('genre', event.target.value)}>
              {GENRE_OPTIONS.map((genre) => (
                <option key={genre.value} value={genre.value}>
                  {t(genre.labelKey)}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-[var(--muted)]">{t('generateV2.episodeCount')}</label>
            <Input
              type="number"
              min={1}
              max={10}
              value={value.episodesCount}
              onChange={(event) => onChange('episodesCount', Number(event.target.value || 1))}
            />
          </div>
        </div>

        <Button onClick={onGenerate} disabled={isPlanning || value.idea.trim().length < 10} className="w-full md:w-auto">
          {isPlanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {t('generate.generateEpisodePrompts')}
        </Button>
      </CardContent>
    </Card>
  );
}
