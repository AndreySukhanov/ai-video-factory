'use client';

import { useState, useRef, useCallback } from 'react';
import { ImagePlus, X, AlertTriangle } from 'lucide-react';
import { useLanguage } from '@/contexts/LanguageContext';
import { apiFetch } from '@/lib/apiBase';

interface ImageUploadProps {
    onImageUploaded: (url: string) => void;
    onImageRemoved?: () => void;
    apiBaseUrl?: string;
    compact?: boolean;  // Compact mode for grid layouts
}

export default function ImageUpload({
    onImageUploaded,
    onImageRemoved,
    apiBaseUrl = 'http://localhost:8000',
    compact = false
}: ImageUploadProps) {
    const { t } = useLanguage();
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [preview, setPreview] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const uploadFile = async (file: File) => {
        setError(null);
        setIsUploading(true);

        // Validate file type
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
        if (!allowedTypes.includes(file.type)) {
            setError(t('imageUpload.invalidType'));
            setIsUploading(false);
            return;
        }

        // Validate file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            setError(t('imageUpload.tooLarge'));
            setIsUploading(false);
            return;
        }

        // Create preview
        const reader = new FileReader();
        reader.onload = (e) => {
            setPreview(e.target?.result as string);
        };
        reader.readAsDataURL(file);

        // Upload file
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await apiFetch(`${apiBaseUrl}/api/v1/upload/image`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Upload failed');
            }

            const data = await response.json();
            setUploadedFilename(data.filename);

            // Return full URL for the video provider
            // If URL is already absolute (catbox), use it directly
            const fullUrl = data.url.startsWith('http') ? data.url : `${apiBaseUrl}${data.url}`;
            onImageUploaded(fullUrl);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Upload failed');
            setPreview(null);
        } finally {
            setIsUploading(false);
        }
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const file = e.dataTransfer.files[0];
        if (file) {
            uploadFile(file);
        }
    }, []);

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            uploadFile(file);
        }
    };

    const handleRemove = async () => {
        if (uploadedFilename) {
            try {
                await apiFetch(`${apiBaseUrl}/api/v1/upload/image/${uploadedFilename}`, {
                    method: 'DELETE',
                });
            } catch (err) {
                console.error('Failed to delete file:', err);
            }
        }

        setPreview(null);
        setUploadedFilename(null);
        setError(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
        onImageRemoved?.();
    };

    return (
        <div className="w-full">
            {!preview ? (
                <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`
                        border-2 border-dashed rounded-xl text-center cursor-pointer
                        transition-all duration-200
                        ${compact ? 'p-2 h-24 flex flex-col items-center justify-center' : 'p-8'}
                        ${isDragging
                            ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                            : 'border-gray-300 dark:border-gray-600 hover:border-teal-400 dark:hover:border-teal-500'
                        }
                        ${isUploading ? 'opacity-50 pointer-events-none' : ''}
                    `}
                >
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif"
                        onChange={handleFileSelect}
                        className="hidden"
                    />

                    {isUploading ? (
                        <div className="flex flex-col items-center gap-2">
                            <div className={`border-3 border-teal-500 border-t-transparent rounded-full animate-spin ${compact ? 'w-6 h-6' : 'w-10 h-10'}`} />
                            {!compact && <p className="text-gray-500">{t('imageUpload.uploading')}</p>}
                        </div>
                    ) : (
                        <>
                            <ImagePlus className={`mx-auto text-gray-400 ${compact ? 'w-6 h-6 mb-1' : 'w-10 h-10 mb-3'}`} />
                            {compact ? (
                                <p className="text-gray-500 text-xs">{t('imageUpload.add')}</p>
                            ) : (
                                <>
                                    <p className="text-gray-600 dark:text-gray-300 font-medium">
                                        {t('imageUpload.dropOrClick')}
                                    </p>
                                    <p className="text-sm text-gray-400 mt-2">
                                        {t('imageUpload.formats')}
                                    </p>
                                </>
                            )}
                        </>
                    )}
                </div>
            ) : (
                <div className={`relative rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700`}>
                    <img
                        src={preview}
                        alt="Preview"
                        className={`w-full object-cover ${compact ? 'h-24' : 'h-48'}`}
                    />
                    <button
                        onClick={handleRemove}
                        className={`absolute top-1 right-1 bg-red-500 hover:bg-red-600 text-white rounded-full flex items-center justify-center shadow-lg transition-colors ${compact ? 'w-5 h-5' : 'w-8 h-8'}`}
                    >
                        <X className={compact ? 'w-3 h-3' : 'w-4 h-4'} />
                    </button>
                    {!compact && (
                        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3">
                            <p className="text-white text-sm font-medium">{t('imageUpload.referenceImage')}</p>
                        </div>
                    )}
                </div>
            )}

            {error && (
                <p className={`text-red-500 mt-2 flex items-center gap-1 ${compact ? 'text-xs' : 'text-sm'}`}><AlertTriangle className="w-3 h-3" /> {error}</p>
            )}
        </div>
    );
}
