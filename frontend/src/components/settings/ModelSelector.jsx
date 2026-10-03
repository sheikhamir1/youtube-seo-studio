import { AudioLines, Info } from 'lucide-react';

import { cn } from '../../utils/cn';
import Badge from '../ui/Badge';
import { LoadingBlock } from '../ui/Spinner';

/**
 * Model picker driven by the backend model registry, so a model that cannot
 * accept audio input can never be selected for this pipeline.
 */
export function ModelSelector({ models = [], value, onChange, defaultModel, isLoading = false, disabled = false }) {
  if (isLoading) return <LoadingBlock label="Loading model registry…" />;

  const selectable = models.filter((model) => model.supports_audio && model.is_configured);

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        {selectable.map((model) => {
          const selected = model.id === value;
          return (
            <button
              key={model.id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(model.id)}
              className={cn(
                'rounded-md border p-3 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60',
                selected ? 'border-accent bg-accent/8' : 'border-border hover:bg-surface-2',
              )}
              aria-pressed={selected}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{model.label}</span>
                <div className="flex items-center gap-1">
                  {model.is_default && <Badge variant="accent">default</Badge>}
                  {!model.capability_known && <Badge variant="warning">unverified</Badge>}
                </div>
              </div>
              <p className="mono mt-1 text-xs text-muted">{model.id}</p>
              <p className="mt-1 flex items-center gap-1.5 text-xs text-muted">
                <AudioLines className="h-3 w-3" aria-hidden="true" />
                audio input supported
                {model.supports_structured_output ? ' · structured output' : ''}
              </p>
              {model.notes && <p className="mt-1 text-xs text-muted">{model.notes}</p>}
            </button>
          );
        })}
      </div>

      {models.some((model) => !model.supports_audio || !model.is_configured) && (
        <p className="flex items-start gap-1.5 text-xs text-muted">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {models.filter((model) => !model.supports_audio || !model.is_configured).length} registered
          model(s) cannot be selected: this pipeline requires audio input, and a model must also be
          enabled in GEMINI_ALLOWED_MODELS.
        </p>
      )}

      {defaultModel && value !== defaultModel && (
        <p className="text-xs text-muted">
          Default model is <span className="mono">{defaultModel}</span> (from GEMINI_MODEL).
        </p>
      )}
    </div>
  );
}

export default ModelSelector;
