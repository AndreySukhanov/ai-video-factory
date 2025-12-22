'use client';

import { useState, useRef, useCallback } from 'react';
import { ImagePlus, X, AlertTriangle } from 'lucide-react';

interface ImageUploadProps {
    onImageUploaded: (url: string) => void;
    onImageRemoved?: () => void;
    apiBaseUrl?: string;
}

export default function ImageUpload({
    onImageUploaded,
    onImageRemoved,
    apiBaseUrl = 'http://localhost:8000'
}: ImageUploadProps) {
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
            setError('Invalid file type. Use JPG, PNG, WebP, or GIF.');
            setIsUploading(false);
            return;
        }

        // Validate file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            setError('File too large. Maximum size is 10MB.');
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

            const response = await fetch(`${apiBaseUrl}/api/v1/upload/image`, {
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
            const fullUrl = `${apiBaseUrl}${data.url}`;
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
                await fetch(`${apiBaseUrl}/api/v1/upload/image/${uploadedFilename}`, {
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
                        border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
                        transition-all duration-200
                        ${isDragging
                            ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/20'
                            : 'border-gray-300 dark:border-gray-600 hover:border-purple-400 dark:hover:border-purple-500'
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
                        <div className="flex flex-col items-center gap-3">
                            <div className="w-10 h-10 border-3 border-purple-500 border-t-transparent rounded-full animate-spin" />
                            <p className="text-gray-500">Uploading...</p>
                        </div>
                    ) : (
                        <>
                            <ImagePlus className="w-10 h-10 mx-auto mb-3 text-gray-400" />
                            <p className="text-gray-600 dark:text-gray-300 font-medium">
                                Drop image here or click to upload
                            </p>
                            <p className="text-sm text-gray-400 mt-2">
                                JPG, PNG, WebP, GIF • Max 10MB
                            </p>
                        </>
                    )}
                </div>
            ) : (
                <div className="relative rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700">
                    <img
                        src={preview}
                        alt="Preview"
                        className="w-full h-48 object-cover"
                    />
                    <button
                        onClick={handleRemove}
                        className="absolute top-2 right-2 bg-red-500 hover:bg-red-600 text-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-3">
                        <p className="text-white text-sm font-medium">Reference Image</p>
                    </div>
                </div>
            )}

            {error && (
                <p className="text-red-500 text-sm mt-2 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> {error}</p>
            )}
        </div>
    );
}
