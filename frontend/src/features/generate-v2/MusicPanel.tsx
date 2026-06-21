'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2, Music } from 'lucide-react';
import { Button, Select } from '@/components/ui';
import { useLanguage } from '@/contexts/LanguageContext';
import {
  addMusicToVideo,
  listMusicTracks,
  type MusicTrack,
} from '@/lib/api/generation';

interface MusicPanelProps {
  videoUrl: string | null;
}

export default function MusicPanel({ videoUrl }: MusicPanelProps) {
  const { t } = useLanguage();
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loadingTracks, setLoadingTracks] = useState(true);
  const [tracksError, setTracksError] = useState<string | null>(null);
  const [selectedMood, setSelectedMood] = useState<string>('');
  const [selectedTrackId, setSelectedTrackId] = useState<string>('');
  const [volume, setVolume] = useState(0.15);
  const [loopMusic, setLoopMusic] = useState(true);
  const [fadeIn, setFadeIn] = useState(1);
  const [fadeOut, setFadeOut] = useState(1.5);
  const [mixing, setMixing] = useState(false);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [mixError, setMixError] = useState<string | null>(null);

  useEffect(() => {
    listMusicTracks()
      .then((r) => {
        setTracks(r.tracks);
        if (r.tracks.length > 0) setSelectedTrackId(r.tracks[0].id);
      })
      .catch((e) => setTracksError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoadingTracks(false));
  }, []);

  const moods = useMemo(() => {
    return Array.from(new Set(tracks.map((tr) => tr.mood))).sort();
  }, [tracks]);

  const filtered = useMemo(() => {
    return selectedMood ? tracks.filter((tr) => tr.mood === selectedMood) : tracks;
  }, [tracks, selectedMood]);

  useEffect(() => {
    if (filtered.length > 0 && !filtered.find((tr) => tr.id === selectedTrackId)) {
      setSelectedTrackId(filtered[0].id);
    }
  }, [filtered, selectedTrackId]);

  const handleMix = async () => {
    if (!videoUrl || !selectedTrackId) return;
    setMixError(null);
    setMixing(true);
    try {
      const resp = await addMusicToVideo({
        video_url: videoUrl,
        track_id: selectedTrackId,
        volume,
        loop_music: loopMusic,
        fade_in: fadeIn,
        fade_out: fadeOut,
      });
      if (!resp.success || !resp.video_with_music_url) {
        setMixError(resp.error || t('generateV2.musicError'));
        setResultUrl(null);
        return;
      }
      setResultUrl(resp.video_with_music_url);
    } catch (e) {
      setMixError(e instanceof Error ? e.message : String(e));
      setResultUrl(null);
    } finally {
      setMixing(false);
    }
  };

  return (
    <div className="space-y-3 rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-1)] p-4">
      <div className="flex items-center gap-2">
        <Music className="w-4 h-4 text-[var(--brand-1)]" />
        <h3 className="text-sm font-medium text-white">{t('generateV2.musicTitle')}</h3>
      </div>
      <p className="text-xs text-[var(--muted)]">{t('generateV2.musicDescription')}</p>

      {loadingTracks && (
        <p className="text-xs text-[var(--muted)] flex items-center gap-2">
          <Loader2 className="w-3 h-3 animate-spin" /> ...
        </p>
      )}

      {tracksError && <p className="text-sm text-red-400">{t('generateV2.musicTracksLoadError')}: {tracksError}</p>}

      {!loadingTracks && tracks.length === 0 && !tracksError && (
        <p className="text-xs text-amber-300">{t('generateV2.musicNoTracks')}</p>
      )}

      {tracks.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.musicMood')}</label>
              <Select value={selectedMood} onChange={(e) => setSelectedMood(e.target.value)}>
                <option value="">{t('generateV2.musicMoodAll')}</option>
                {moods.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.musicTrack')}</label>
              <Select value={selectedTrackId} onChange={(e) => setSelectedTrackId(e.target.value)}>
                {filtered.map((tr) => (
                  <option key={tr.id} value={tr.id}>
                    {tr.display_name}{tr.duration_sec ? ` · ${tr.duration_sec.toFixed(0)}s` : ''}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-[var(--muted)]">
              {t('generateV2.musicVolume')}: {(volume * 100).toFixed(0)}%
            </label>
            <input
              type="range" min="0" max="1" step="0.05"
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-full"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.musicFadeIn')}</label>
              <input
                type="number" min="0" max="10" step="0.5"
                value={fadeIn}
                onChange={(e) => setFadeIn(parseFloat(e.target.value) || 0)}
                className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-2)] p-2 text-sm text-white"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-[var(--muted)]">{t('generateV2.musicFadeOut')}</label>
              <input
                type="number" min="0" max="10" step="0.5"
                value={fadeOut}
                onChange={(e) => setFadeOut(parseFloat(e.target.value) || 0)}
                className="w-full rounded-[var(--radius-sm)] border border-white/10 bg-[var(--surface-2)] p-2 text-sm text-white"
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
            <input
              type="checkbox"
              checked={loopMusic}
              onChange={(e) => setLoopMusic(e.target.checked)}
              className="rounded border-white/20 bg-[var(--surface-2)]"
            />
            {t('generateV2.musicLoop')}
          </label>

          <Button onClick={handleMix} disabled={!videoUrl || !selectedTrackId || mixing} variant="secondary">
            {mixing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('generateV2.musicAdding')}
              </>
            ) : (
              <>
                <Music className="w-4 h-4" />
                {t('generateV2.musicAdd')}
              </>
            )}
          </Button>

          {mixError && <p className="text-sm text-red-400">{mixError}</p>}

          {resultUrl && (
            <div className="space-y-2">
              <label className="text-xs text-green-400 font-medium">{t('generateV2.musicReady')}</label>
              <video
                src={resultUrl}
                controls
                className="w-full max-h-[400px] rounded-[var(--radius-sm)] bg-black"
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
