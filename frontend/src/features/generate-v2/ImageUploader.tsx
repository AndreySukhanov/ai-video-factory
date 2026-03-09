import { useCallback, useRef, useState } from 'react';
import { Upload, X, Loader2 } from 'lucide-react';
import { uploadImage } from '@/lib/api/generation';
import { useLanguage } from '@/contexts/LanguageContext';

export interface UploadedImage {
  url: string;       // external catbox URL (for video gen APIs)
  localUrl: string;  // local path /uploads/xxx.jpg (for backend storyboard)
}

interface ImageUploaderProps {
  label: string;
  currentUrl?: string;
  onUploaded: (img: UploadedImage) => void;
  onRemove: () => void;
}

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

export default function ImageUploader({ label, currentUrl, onUploaded, onRemove }: ImageUploaderProps) {
  const { t } = useLanguage();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(t('generateV2.uploadInvalidType'));
      return;
    }
    if (file.size > MAX_SIZE) {
      setError(t('generateV2.uploadTooLarge'));
      return;
    }
    setIsUploading(true);
    try {
      const result = await uploadImage(file);
      if (result.success && result.url) {
        onUploaded({ url: result.url, localUrl: result.local_url });
      } else {
        setError(t('generateV2.uploadFailed'));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('generateV2.uploadFailed'));
    } finally {
      setIsUploading(false);
    }
  }, [onUploaded, t]);

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    if (inputRef.current) inputRef.current.value = '';
  }, [handleFile]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, [handleFile]);

  if (currentUrl) {
    return (
      <div className="space-y-1">
        <label className="text-xs text-[var(--muted)]">{label}</label>
        <div className="relative inline-block">
          <img
            src={currentUrl}
            alt={label}
            className="w-24 h-24 object-cover rounded-lg border border-white/10"
          />
          <button
            type="button"
            onClick={onRemove}
            className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-400 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <label className="text-xs text-[var(--muted)]">{label}</label>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        disabled={isUploading}
        className={`w-full h-24 rounded-lg border border-dashed flex flex-col items-center justify-center gap-1 text-xs transition-colors cursor-pointer
          ${dragOver ? 'border-[var(--brand-1)] bg-[var(--brand-1)]/10 text-white' : 'border-white/15 bg-white/5 text-[var(--muted)] hover:border-white/30 hover:text-white'}
          ${isUploading ? 'opacity-50 cursor-wait' : ''}`}
      >
        {isUploading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <Upload className="w-5 h-5" />
        )}
        <span>{isUploading ? t('generateV2.uploading') : t('generateV2.dragDropHint')}</span>
      </button>
      <input ref={inputRef} type="file" accept="image/*" onChange={onFileChange} className="hidden" />
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  );
}
