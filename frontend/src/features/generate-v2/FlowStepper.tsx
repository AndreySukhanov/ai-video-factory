import { FlowStep, FlowStepId } from './types';
import { cn } from '@/lib/utils';
import { useLanguage } from '@/contexts/LanguageContext';

interface FlowStepperProps {
  steps: FlowStep[];
  currentStep: FlowStepId;
  onStepClick: (step: FlowStepId) => void;
}

export default function FlowStepper({ steps, currentStep, onStepClick }: FlowStepperProps) {
  const { t } = useLanguage();
  const activeIndex = steps.findIndex((step) => step.id === currentStep);
  return (
    <ol className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {steps.map((step, index) => {
        const isActive = step.id === currentStep;
        const isPast = index < activeIndex;
        return (
          <li key={step.id}>
            <button
              type="button"
              onClick={() => onStepClick(step.id)}
              className={cn(
                'w-full rounded-[var(--radius-md)] border p-3 text-left transition-colors',
                isActive && 'border-[var(--brand-1)] bg-[var(--surface-2)]',
                isPast && 'border-[var(--brand-2)]/50 bg-[var(--surface-1)]',
                !isActive && !isPast && 'border-white/10 bg-[var(--surface-1)] hover:bg-[var(--surface-2)]/70',
              )}
            >
              <div className="text-xs text-[var(--muted)]">{t('generateV2.step', { count: index + 1 })}</div>
              <div className="text-sm font-medium text-white mt-0.5">{step.label}</div>
              <div className="text-xs text-[var(--muted)] mt-1 line-clamp-2">{step.hint}</div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
