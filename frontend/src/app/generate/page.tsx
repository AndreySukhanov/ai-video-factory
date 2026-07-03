'use client';

import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import GenerationWizardV2 from '@/features/generate-v2/GenerationWizardV2';

export default function GenerateEpisodePageWrapper() {
    return (
        <Suspense fallback={<div className="min-h-screen bg-gray-900 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-purple-400" /></div>}>
            <GenerationWizardV2 />
        </Suspense>
    );
}
