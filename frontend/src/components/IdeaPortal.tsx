'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, ImagePlus, Link2, X, Loader2, ArrowUpRight } from 'lucide-react';
import { uploadImage } from '@/lib/api/generation';
import { useLanguage } from '@/contexts/LanguageContext';
import { display } from '@/lib/fonts';

interface IdeaPortalProps {
  open: boolean;
  onClose: () => void;
}

interface PortalImage {
  url: string;      // external catbox URL (video-gen APIs)
  localUrl: string; // local /uploads path (backend storyboard)
  preview: string;  // whatever renders as a thumbnail
}

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
const MIN_IDEA = 10;
const MAX_IDEA = 1000;
const URL_RE = /^https?:\/\/\S+$/i;

// The homepage "portal": a modal window where the user throws text, photos and links.
// It uploads any images, assembles a brief, stashes it in sessionStorage and hands off
// to the existing generation wizard via /generate?source=portal — which auto-plans the series.
export default function IdeaPortal({ open, onClose }: IdeaPortalProps) {
  const { t } = useLanguage();
  const router = useRouter();

  const [idea, setIdea] = useState('');
  const [links, setLinks] = useState<string[]>([]);
  const [linkDraft, setLinkDraft] = useState('');
  const [images, setImages] = useState<PortalImage[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Close on Escape, lock body scroll, and focus the idea field while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusTimer = setTimeout(() => textareaRef.current?.focus(), 60);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prevOverflow;
      clearTimeout(focusTimer);
    };
  }, [open, onClose]);

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const list = Array.from(files).filter((f) => ALLOWED_TYPES.includes(f.type) && f.size <= MAX_SIZE);
    if (list.length === 0) return;
    setError(null);
    setUploading(true);
    try {
      for (const file of list) {
        const res = await uploadImage(file);
        if (res.success && res.url) {
          setImages((prev) => [...prev, { url: res.url, localUrl: res.local_url, preview: res.local_url || res.url }]);
        } else {
          setError(t('home.portalUploadFailed'));
        }
      }
    } catch {
      setError(t('home.portalUploadFailed'));
    } finally {
      setUploading(false);
    }
  }, [t]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    // Files dropped → images. Text/URL dropped → link or idea.
    if (e.dataTransfer.files?.length) {
      void handleFiles(e.dataTransfer.files);
      return;
    }
    const text = e.dataTransfer.getData('text');
    if (text && URL_RE.test(text.trim())) {
      setLinks((prev) => (prev.includes(text.trim()) ? prev : [...prev, text.trim()]));
    } else if (text) {
      setIdea((prev) => (prev ? `${prev} ${text}` : text));
    }
  }, [handleFiles]);

  const onPaste = useCallback((e: React.ClipboardEvent) => {
    const imageItems = Array.from(e.clipboardData.items).filter((i) => i.type.startsWith('image/'));
    if (imageItems.length > 0) {
      e.preventDefault();
      const files = imageItems.map((i) => i.getAsFile()).filter((f): f is File => !!f);
      if (files.length) void handleFiles(files);
    }
  }, [handleFiles]);

  const commitLinkDraft = useCallback(() => {
    const v = linkDraft.trim();
    if (!v) return;
    if (URL_RE.test(v)) {
      setLinks((prev) => (prev.includes(v) ? prev : [...prev, v]));
      setLinkDraft('');
    }
  }, [linkDraft]);

  const removeImage = (url: string) => setImages((prev) => prev.filter((i) => i.url !== url));
  const removeLink = (url: string) => setLinks((prev) => prev.filter((l) => l !== url));

  const canSubmit = idea.trim().length >= MIN_IDEA && !uploading && !submitting;

  const handleSubmit = useCallback(() => {
    if (idea.trim().length < MIN_IDEA) {
      setError(t('home.portalHintShort'));
      return;
    }
    setSubmitting(true);

    // Fold links into the idea text (the LLM planner treats them as inspiration references).
    let assembled = idea.trim();
    if (links.length > 0) {
      const suffix = `\n\nReference links: ${links.join(', ')}`;
      assembled = (assembled + suffix).slice(0, MAX_IDEA);
    } else {
      assembled = assembled.slice(0, MAX_IDEA);
    }

    const brief = {
      idea: assembled,
      reference_images: images.map((i) => i.url),
      reference_local_urls: images.map((i) => i.localUrl),
    };

    try {
      sessionStorage.setItem('portal_brief', JSON.stringify(brief));
    } catch {
      /* storage disabled — the wizard falls back to an empty idea form */
    }
    router.push('/generate?source=portal');
  }, [idea, links, images, router, t]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('home.portalTitle')}
      className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 sm:p-6 overflow-y-auto"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label={t('home.portalClose')}
        onClick={onClose}
        className="absolute inset-0 bg-[#040810]/80 backdrop-blur-sm cursor-default"
      />

      {/* The portal itself: a glowing well that swallows whatever you throw in. */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onPaste={onPaste}
        className={`landing-rise relative w-full max-w-3xl my-auto overflow-hidden rounded-[var(--radius-md)] border transition-all duration-300
          ${dragOver
            ? 'border-[var(--brand-1)] shadow-[0_0_0_1px_var(--brand-1),0_30px_80px_rgba(20,184,166,0.25)]'
            : 'border-white/10 shadow-[0_40px_120px_rgba(4,8,16,0.8)]'}`}
        style={{ animationDelay: '0s' }}
      >
        {/* Close */}
        <button
          type="button"
          onClick={onClose}
          aria-label={t('home.portalClose')}
          className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full flex items-center justify-center text-[var(--muted)] hover:text-white hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* portal glow */}
        <div aria-hidden className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-1/3 left-1/2 -translate-x-1/2 w-[70%] h-[70%] rounded-full bg-[radial-gradient(circle,rgba(20,184,166,0.18),transparent_65%)] blur-2xl" />
          <div className="absolute -bottom-1/4 right-0 w-[40%] h-[50%] rounded-full bg-[radial-gradient(circle,rgba(245,158,11,0.10),transparent_60%)] blur-2xl" />
        </div>

        <div className="relative bg-[var(--surface-1)]/70 backdrop-blur-sm p-5 sm:p-6">
          <div className="mb-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[var(--brand-1)] mb-2">
              ● {t('home.portalKicker')}
            </div>
            <h2 className={`${display.className} text-xl sm:text-2xl font-bold text-white leading-tight`}>
              {t('home.portalTitle')}
            </h2>
            <p className="text-sm text-[var(--muted)] mt-1.5 max-w-2xl">{t('home.portalSub')}</p>
          </div>

          <textarea
            ref={textareaRef}
            value={idea}
            onChange={(e) => { setIdea(e.target.value); if (error) setError(null); }}
            placeholder={t('home.portalPlaceholder')}
            rows={3}
            maxLength={MAX_IDEA}
            className="w-full resize-none bg-black/20 border border-white/10 rounded-[var(--radius-sm)] px-4 py-3 text-[15px] text-white placeholder:text-[var(--muted)]/70 focus:outline-none focus:border-[var(--brand-1)]/60 focus:bg-black/30 transition-colors"
          />

          {/* Reference thumbnails */}
          {images.length > 0 && (
            <div className="mt-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-2">{t('home.portalRefs')}</div>
              <div className="flex flex-wrap gap-2">
                {images.map((img) => (
                  <div key={img.url} className="relative group">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={img.preview} alt="" className="w-16 h-16 object-cover rounded-[var(--radius-sm)] ring-1 ring-white/10" />
                    <button
                      type="button"
                      onClick={() => removeImage(img.url)}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-[var(--danger)] text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-label="Remove"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Link chips */}
          {links.length > 0 && (
            <div className="mt-3">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-2">{t('home.portalLinks')}</div>
              <div className="flex flex-wrap gap-2">
                {links.map((l) => (
                  <span key={l} className="inline-flex items-center gap-1.5 max-w-[240px] bg-[var(--brand-1)]/10 border border-[var(--brand-1)]/30 text-[var(--brand-1)] rounded-full pl-2.5 pr-1.5 py-1 text-xs">
                    <Link2 className="w-3 h-3 shrink-0" />
                    <span className="truncate">{l.replace(/^https?:\/\//, '')}</span>
                    <button type="button" onClick={() => removeLink(l)} className="shrink-0 hover:text-white" aria-label="Remove link">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="mt-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="inline-flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-white border border-white/10 hover:border-white/25 rounded-[var(--radius-sm)] px-3 py-2 transition-colors disabled:opacity-50"
              >
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
                <span className="hidden sm:inline">{uploading ? t('home.portalUploading') : t('home.portalAddImage')}</span>
              </button>
              <div className="relative flex-1 min-w-0">
                <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
                <input
                  type="url"
                  value={linkDraft}
                  onChange={(e) => setLinkDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitLinkDraft(); } }}
                  onBlur={commitLinkDraft}
                  placeholder={t('home.portalAddLink')}
                  className="w-full bg-black/20 border border-white/10 rounded-[var(--radius-sm)] pl-9 pr-3 py-2 text-sm text-white placeholder:text-[var(--muted)]/70 focus:outline-none focus:border-[var(--brand-1)]/60 transition-colors"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="group inline-flex items-center justify-center gap-2 bg-[var(--brand-1)] text-[#04211c] px-6 py-2.5 rounded-[var(--radius-sm)] font-bold text-sm hover:brightness-110 transition-all shadow-[0_16px_40px_rgba(20,184,166,0.22)] disabled:opacity-40 disabled:shadow-none disabled:cursor-not-allowed shrink-0"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {submitting ? t('home.portalSubmitBusy') : t('home.portalSubmit')}
              <ArrowUpRight className="w-4 h-4 opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all" />
            </button>
          </div>

          <div className="mt-3 flex items-center justify-between gap-3 min-h-[16px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">
              {dragOver ? t('home.portalDropHint') : (error ?? '')}
            </span>
            <span className="font-mono text-[10px] text-[var(--muted)]/60">{idea.trim().length}/{MAX_IDEA}</span>
          </div>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => { if (e.target.files) void handleFiles(e.target.files); if (fileInputRef.current) fileInputRef.current.value = ''; }}
      />
    </div>
  );
}
