'use client';

import Link from 'next/link';
import { ArrowLeft, RotateCcw } from 'lucide-react';
import { Button, Toast } from '@/components/ui';
import FlowStepper from './FlowStepper';
import IdeaStep from './IdeaStep';
import EpisodesStep from './EpisodesStep';
import GenerationStep from './GenerationStep';
import StoryboardStep from './StoryboardStep';
import PublishStep from './PublishStep';
import StatusPanel from './StatusPanel';
import { FlowStepId } from './types';
import { useGenerationFlow } from './useGenerationFlow';
import { useLanguage } from '@/contexts/LanguageContext';

export default function GenerationWizardV2() {
  const { t } = useLanguage();
  const flow = useGenerationFlow();

  const handleStepClick = (step: FlowStepId) => {
    if (step === 'idea') {
      flow.goStep(step);
      return;
    }
    if ((step === 'episodes' || step === 'storyboard' || step === 'generation') && flow.episodes.length === 0) {
      return;
    }
    if (step === 'publish' && flow.stats.done === 0) {
      return;
    }
    flow.goStep(step);
  };

  return (
    <div className="min-h-screen p-4 md:p-6 [--brand-1:#a855f7] [--brand-2:#ec4899]">
      <div className="max-w-[1440px] mx-auto space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-[var(--muted)] hover:text-white mb-2">
              <ArrowLeft className="w-4 h-4" /> {t('generateV2.backToHome')}
            </Link>
            <h1 className="text-3xl md:text-4xl font-semibold">{t('generateV2.title')}</h1>
            <p className="text-[var(--muted)] text-sm mt-1">{t('generateV2.subtitle')}</p>
          </div>
          <Button variant="ghost" onClick={flow.resetFlow}>
            <RotateCcw className="w-4 h-4" /> {t('generateV2.resetDraft')}
          </Button>
        </div>

        <FlowStepper steps={flow.steps} currentStep={flow.currentStep} onStepClick={handleStepClick} />

        {flow.error && <Toast kind="error" title={t('generateV2.actionFailed')} message={flow.error} />}
        {flow.notice && <Toast kind="success" title={t('generateV2.update')} message={flow.notice} />}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            {flow.currentStep === 'idea' && (
              <IdeaStep value={flow.ideaForm} isPlanning={flow.isPlanning} onChange={flow.updateIdeaForm} onGenerate={flow.planEpisodes} />
            )}

            {flow.currentStep === 'episodes' && (
              <EpisodesStep
                seriesTitle={flow.seriesTitle}
                seriesLogline={flow.seriesLogline}
                ideaForm={flow.ideaForm}
                episodes={flow.episodes}
                onIdeaChange={flow.updateIdeaForm}
                onEpisodeChange={flow.updateEpisodeField}
                onRunGeneration={flow.runQueue}
                onRunStoryboard={flow.runStoryboard}
                isStoryboarding={flow.isStoryboarding}
                storyboardFrames={flow.storyboardFrames}
                imageModel={flow.imageModel}
                onImageModelChange={flow.setImageModel}
                referenceImages={flow.referenceImages}
                onReferenceImagesChange={flow.setReferenceImages}
                referenceLocalUrls={flow.referenceLocalUrls}
                onReferenceLocalUrlsChange={flow.setReferenceLocalUrls}
              />
            )}

            {flow.currentStep === 'storyboard' && (
              <StoryboardStep
                episodes={flow.episodes}
                storyboardFrames={flow.storyboardFrames}
                imageModel={flow.imageModel}
                isStoryboarding={flow.isStoryboarding}
                onImageModelChange={flow.setImageModel}
                onRunStoryboard={flow.runStoryboard}
                onRegenerateFrame={flow.regenerateFrame}
                onSetEpisodeFirstFrame={flow.setEpisodeFirstFrame}
                onContinue={() => flow.goStep('generation')}
              />
            )}

            {flow.currentStep === 'generation' && (
              <GenerationStep
                episodes={flow.episodes}
                isGenerating={flow.isGenerating}
                onRunQueue={flow.runQueue}
                onRetryEpisode={flow.retryEpisode}
                onMoveEpisode={flow.moveEpisode}
                onRegenerateEpisode={flow.regenerateEpisode}
                defaultModel={flow.ideaForm.model}
                episodesCount={flow.ideaForm.episodesCount}
                onSetEpisodeModel={flow.setEpisodeModel}
                onApplyModelToAll={flow.applyModelToAll}
              />
            )}

            {flow.currentStep === 'publish' && (
              <PublishStep
                episodes={flow.episodes}
                form={flow.publishForm}
                isPublishing={flow.isPublishing}
                isStitching={flow.isStitching}
                stitchedVideoUrl={flow.stitchedVideoUrl}
                stitchedDuration={flow.stitchedDuration}
                onSelectEpisode={flow.selectPublishEpisode}
                onChange={flow.updatePublishForm}
                onStitch={flow.stitchEpisodes}
                onPublish={flow.publishToReview}
              />
            )}
          </div>

          <StatusPanel
            currentStep={flow.currentStep}
            episodes={flow.episodes}
            isGenerating={flow.isGenerating}
            onRetryEpisode={flow.retryEpisode}
            onDeleteEpisode={flow.removeEpisode}
            onMoveEpisode={flow.moveEpisode}
            onRegenerateEpisode={flow.regenerateEpisode}
          />
        </div>
      </div>
    </div>
  );
}
