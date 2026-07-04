'use client';

import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import GenerationWizardV2 from '@/features/generate-v2/GenerationWizardV2';
import FeatureErrorBoundary from '@/components/FeatureErrorBoundary';

export default function GenerateEpisodePageWrapper() {
    return (
        <FeatureErrorBoundary featureName="Generation Wizard">
            <Suspense fallback={<div className="min-h-screen bg-gray-900 flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-teal-400" /></div>}>
                <GenerationWizardV2 />
            </Suspense>
        </FeatureErrorBoundary>
    );
}
