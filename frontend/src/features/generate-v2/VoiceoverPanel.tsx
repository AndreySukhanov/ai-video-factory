'use client';

import { useState } from 'react';
import { Captions, Loader2, Mic, Volume2 } from 'lucide-react';
import { Button, Input, Select } from '@/components/ui';
import { useLanguage } from '@/contexts/LanguageContext';
import {
  burnCaptions,
  generateVoiceover,
  type CaptionMode,
  type CaptionStyle,
  type VoiceoverProvider,
  type VoiceoverResponse,
} from '@/lib/api/generation';

interface VoiceoverPanelProps {
  videoUrl: string | null;
}

export default function VoiceoverPanel({ videoUrl }: VoiceoverPanelProps) {
  const { t } = useLanguage();
  const [text, setText] = useState('');
  const [provider, setProvider] = useState<VoiceoverProvider>('elevenlabs');
  const [voiceId, setVoiceId] = useState('');
  const [muteOriginal, setMuteOriginal] = useState(true);
  const [loading, setLoading] = useState(false);
  const [muxing, setMuxing] = useState(false);
  const [result, setResult] = useState<VoiceoverResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [captionStyle, setCaptionStyle] = useState<CaptionStyle>('modern');
  const [captionMode, setCaptionMode] = useState<CaptionMode>('word_pop');
  const [burning, setBurning] = useState(false);
  const [captionsUrl, setCaptionsUrl] = useState<string | null>(null);
  const [captionsError, setCaptionsError] = useState<string | null>(null);

  const handleGenerate = async (withMux: boolean) => {
    if (!text.trim()) return;
    setError(null);
    if (withMux) setMuxing(true);
    else setLoading(true);
    try {
      const resp = await generateVoiceover({
        text: text.trim(),
        provider,
        voice_id: voiceId.trim() || undefined,
        video_url: withMux && videoUrl ? videoUrl : undefined,
        mute_original: muteOriginal,
      });
      if (!resp.success) {
        setError(resp.error || t('generateV2.voiceoverError'));
        setResult(null);
        return;
      }
      setResult(resp);
      setCaptionsUrl(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setLoading(false);
      setMuxing(false);
    }
  };

  const handleBurnCaptions = async () => {
    if (!result?.words?.length) return;
    const targetVideo = result.video_with_voiceover_url || videoUrl;
    if (!targetVideo) return;
    setCaptionsError(null);
    setBurning(true);
    try {
      const resp = await burnCaptions({
        video_url: targetVideo,
        words: result.words,
        style: captionStyle,
        mode: captionMode,
      });
      if (!resp.success || !resp.video_with_captions_url) {
        setCaptionsError(resp.error || t('generateV2.captionsError'));
        setCaptionsUrl(null);
        return;
      }
      setCaptionsUrl(resp.video_with_captions_url);
    } catch (e) {
      setCaptionsError(e instanceof Error ? e.message : String(e));
      setCaptionsUrl(null);
    } finally {
      setBurning(false);
    }
  };

  return (
    <div className="space-y-3 rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-4">
      <div className="flex items-center gap-2">
        <Mic className="w-4 h-4 text-[var(--brand-1)]" />
        <h3 className="text-sm font-medium text-white">{t('generateV2.voiceoverTitle')}</h3>
      </div>
      <p className="text-xs text-[var(--muted)]">{t('generateV2.voiceoverDescription')}</p>

      <div className="space-y-2">
        <label className="text-xs text-[var(--muted)]">{t('generateV2.voiceoverProvider')}</label>
        <Select value={provider} onChange={(e) => setProvider(e.target.value as VoiceoverProvider)}>
          <option value="elevenlabs">{t('generateV2.voiceoverProviderElevenLabs')}</option>
          <option value="openai">{t('generateV2.voiceoverProviderOpenAI')}</option>
        </Select>
      </div>

      <div className="space-y-2">
        <label className="text-xs text-[var(--muted)]">{t('generateV2.voiceoverVoiceId')}</label>
        <Input
          value={voiceId}
          onChange={(e) => setVoiceId(e.target.value)}
          placeholder={provider === 'elevenlabs' ? 'yl2ZDV1MzN4HbQJbMihG' : 'alloy'}
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs text-[var(--muted)]">{t('generateV2.voiceoverText')}</label>
        <textarea
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-2)] p-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-1)]/60"
          placeholder={t('generateV2.voiceoverTextPlaceholder')}
        />
      </div>

      <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
        <input
          type="checkbox"
          checked={muteOriginal}
          onChange={(e) => setMuteOriginal(e.target.checked)}
          className="rounded border-white/20 bg-[var(--surface-2)]"
        />
        {t('generateV2.voiceoverMute')}
      </label>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => handleGenerate(false)} disabled={!text.trim() || loading || muxing} variant="secondary">
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              {t('generateV2.voiceoverGenerating')}
            </>
          ) : (
            <>
              <Volume2 className="w-4 h-4" />
              {t('generateV2.voiceoverGenerate')}
            </>
          )}
        </Button>
        {videoUrl && (
          <Button onClick={() => handleGenerate(true)} disabled={!text.trim() || loading || muxing}>
            {muxing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('generateV2.voiceoverApplying')}
              </>
            ) : (
              <>
                <Mic className="w-4 h-4" />
                {t('generateV2.voiceoverApply')}
              </>
            )}
          </Button>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      {result?.audio_url && (
        <div className="space-y-2">
          <label className="text-xs text-green-400 font-medium">
            {t('generateV2.voiceoverReady')}
            {result.duration_sec != null && (
              <> · {result.duration_sec.toFixed(1)}s · {result.provider}</>
            )}
          </label>
          <audio src={result.audio_url} controls className="w-full" />
        </div>
      )}

      {result?.video_with_voiceover_url && (
        <div className="space-y-2">
          <label className="text-xs text-green-400 font-medium">{t('generateV2.voiceoverFinal')}</label>
          <video
            src={result.video_with_voiceover_url}
            controls
            className="w-full max-h-[400px] rounded-[var(--radius-sm)] bg-black"
          />
        </div>
      )}

      {result?.words && result.words.length > 0 && (
        <div className="space-y-3 mt-3 pt-3 border-t border-white/10">
          <div className="flex items-center gap-2">
            <Captions className="w-4 h-4 text-[var(--brand-1)]" />
            <h4 className="text-sm font-medium text-white">{t('generateV2.captionsTitle')}</h4>
          </div>
          <p className="text-xs text-[var(--muted)]">{t('generateV2.captionsDescription')}</p>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.captionsStyle')}</label>
              <Select value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value as CaptionStyle)}>
                <option value="modern">{t('generateV2.captionsStyleModern')}</option>
                <option value="neon">{t('generateV2.captionsStyleNeon')}</option>
                <option value="bold">{t('generateV2.captionsStyleBold')}</option>
                <option value="minimal">{t('generateV2.captionsStyleMinimal')}</option>
                <option value="cinematic">{t('generateV2.captionsStyleCinematic')}</option>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.captionsMode')}</label>
              <Select value={captionMode} onChange={(e) => setCaptionMode(e.target.value as CaptionMode)}>
                <option value="word_pop">{t('generateV2.captionsModeWordPop')}</option>
                <option value="karaoke_line">{t('generateV2.captionsModeKaraoke')}</option>
              </Select>
            </div>
          </div>

          <Button onClick={handleBurnCaptions} disabled={burning} variant="secondary">
            {burning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('generateV2.captionsBurning')}
              </>
            ) : (
              <>
                <Captions className="w-4 h-4" />
                {t('generateV2.captionsBurn')}
              </>
            )}
          </Button>

          {captionsError && <p className="text-sm text-red-400">{captionsError}</p>}

          {captionsUrl && (
            <div className="space-y-2">
              <label className="text-xs text-green-400 font-medium">{t('generateV2.captionsReady')}</label>
              <video
                src={captionsUrl}
                controls
                className="w-full max-h-[400px] rounded-[var(--radius-sm)] bg-black"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
