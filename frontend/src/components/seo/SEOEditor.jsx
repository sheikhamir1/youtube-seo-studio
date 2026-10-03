import { CheckCircle2, RotateCcw, Save } from 'lucide-react';
import { useMemo, useState } from 'react';

import { DESCRIPTION_MAX_CHARS, DESCRIPTION_WARNING_CHARS, TITLE_MAX_CHARS } from '../../constants';
import { useSaveResultMutation } from '../../queries/results';
import { useToastStore } from '../../stores/toastStore';
import { validateChapters } from '../../utils/chapters';
import { describeApiError } from '../../utils/errors';
import { cn } from '../../utils/cn';
import { useUnsavedChanges } from '../../hooks/useUnsavedChanges';
import Alert from '../ui/Alert';
import Button from '../ui/Button';
import { Card, CardBody, CardFooter, CardHeader } from '../ui/Card';
import CopyButton from '../ui/CopyButton';
import Input, { Textarea } from '../ui/Input';
import Tabs from '../ui/Tabs';
import ChapterValidationPanel from './ChapterValidationPanel';
import ScoreGauge from './ScoreGauge';
import TagsEditor from './TagsEditor';
import ThumbnailPromptPanel from './ThumbnailPromptPanel';
import ImprovementSuggestions from './ImprovementSuggestions';

const TABS = [
  { value: 'title', label: 'Title & score' },
  { value: 'description', label: 'Description' },
  { value: 'tags', label: 'Tags' },
];

/**
 * Fully editable SEO result. Client validation mirrors the backend rules
 * (title ≤ 100 chars, description ≤ 5000 chars, chapter rules) and the backend
 * re-validates every save.
 */
export function SEOEditor({ jobId, result, videoDurationSeconds, onSaved }) {
  const [activeTab, setActiveTab] = useState('title');
  const [form, setForm] = useState(() => ({
    title: result?.title || '',
    description: result?.description || '',
    tags: result?.tags || [],
    thumbnail_prompt: result?.thumbnail_prompt || '',
    improvement_suggestions: result?.improvement_suggestions || '',
  }));
  const [dirty, setDirty] = useState(false);
  const [serverErrors, setServerErrors] = useState(null);
  const saveMutation = useSaveResultMutation(jobId);
  const pushToast = useToastStore((state) => state.push);

  useUnsavedChanges(dirty);

  const update = (field, value) => {
    setForm((previous) => ({ ...previous, [field]: value }));
    setDirty(true);
  };

  const chapterReport = useMemo(
    () => validateChapters(form.description, { videoDurationSeconds }),
    [form.description, videoDurationSeconds],
  );

  const titleLength = form.title.length;
  const descriptionLength = form.description.length;

  const titleError =
    titleLength > TITLE_MAX_CHARS
      ? `Title is ${titleLength} characters; the limit is ${TITLE_MAX_CHARS}.`
      : !form.title.trim()
        ? 'Title must not be empty.'
        : null;

  const descriptionError =
    descriptionLength > DESCRIPTION_MAX_CHARS
      ? `Description is ${descriptionLength} characters; the limit is ${DESCRIPTION_MAX_CHARS}.`
      : !form.description.trim()
        ? 'Description must not be empty.'
        : null;

  const canSave = dirty && !titleError && !descriptionError && !saveMutation.isPending;

  const handleSave = async () => {
    if (!canSave) return;
    setServerErrors(null);
    try {
      const response = await saveMutation.mutateAsync({
        resultId: result.id,
        payload: {
          title: form.title,
          description: form.description,
          tags: form.tags,
          thumbnail_prompt: form.thumbnail_prompt,
          improvement_suggestions: form.improvement_suggestions,
        },
      });
      setDirty(false);
      pushToast({
        variant: 'success',
        title: 'Saved',
        description: 'The edited metadata replaced this version.',
      });
      onSaved?.(response?.data);
    } catch (error) {
      const { title, detail, code } = describeApiError(error);
      const fieldErrors = error?.response?.data?.error?.details;
      setServerErrors({ title, detail, code, fieldErrors });
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  if (!result) return null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Generated SEO metadata"
          description={`Version ${result.version_number} · ${result.model}${
            result.prompt_template_name_snapshot ? ` · ${result.prompt_template_name_snapshot}` : ''
          }`}
          actions={
            <>
              {dirty && (
                <span className="text-xs text-warning" role="status">
                  Unsaved changes
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                icon={RotateCcw}
                disabled={!dirty}
                onClick={() => {
                  setForm({
                    title: result.title || '',
                    description: result.description || '',
                    tags: result.tags || [],
                    thumbnail_prompt: result.thumbnail_prompt || '',
                    improvement_suggestions: result.improvement_suggestions || '',
                  });
                  setDirty(false);
                }}
              >
                Revert
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={Save}
                disabled={!canSave}
                isLoading={saveMutation.isPending}
                onClick={handleSave}
              >
                Save changes
              </Button>
            </>
          }
        />

        <CardBody className="space-y-4">
          <ScoreGauge score={result.seo_score} />

          {serverErrors && (
            <Alert variant="error" title={serverErrors.title}>
              {serverErrors.detail ||
                'The backend rejected this update. Fix the highlighted field and save again.'}
            </Alert>
          )}

          <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />

          {activeTab === 'title' && (
            <div className="space-y-4 pt-1">
              <Input
                label="Video title"
                value={form.title}
                error={titleError}
                onChange={(event) => update('title', event.target.value)}
                rightAddon={
                  <span className={cn('mono', titleLength > TITLE_MAX_CHARS && 'text-danger')}>
                    {titleLength}/{TITLE_MAX_CHARS}
                  </span>
                }
                hint="Keep the primary keyword early; YouTube truncates around 60-70 characters."
              />
              <div className="flex flex-wrap gap-2">
                <CopyButton value={form.title} label="Copy title" />
              </div>
            </div>
          )}

          {activeTab === 'description' && (
            <div className="space-y-4 pt-1">
              <Textarea
                label="Video description"
                value={form.description}
                error={descriptionError}
                onChange={(event) => update('description', event.target.value)}
                className="min-h-[320px] font-mono text-[13px]"
                maxLength={DESCRIPTION_MAX_CHARS}
              />
              {descriptionLength > DESCRIPTION_WARNING_CHARS &&
                descriptionLength <= DESCRIPTION_MAX_CHARS && (
                  <Alert variant="warning" title="Approaching the description limit">
                    {descriptionLength} of {DESCRIPTION_MAX_CHARS} characters used.
                  </Alert>
                )}
              <div className="flex flex-wrap items-center gap-2">
                <CopyButton value={form.description} label="Copy description" />
                <span className="text-xs text-muted">
                  {chapterReport.chapters.length} chapter timestamps detected
                </span>
              </div>
            </div>
          )}

          {activeTab === 'tags' && (
            <div className="pt-1">
              <TagsEditor tags={form.tags} onChange={(tags) => update('tags', tags)} />
            </div>
          )}

          <div className="border-t border-border pt-4">
            <ChapterValidationPanel
              validation={result.validation_metadata}
              chapters={result.chapters || chapterReport.chapters}
            />
          </div>
        </CardBody>

        <CardFooter>
          <p className="text-xs text-muted">
            Saved edits update this version in place; regeneration always creates a new version.
          </p>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
            Backend re-validates on save
          </span>
        </CardFooter>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <ThumbnailPromptPanel prompt={form.thumbnail_prompt} />
        <ImprovementSuggestions suggestions={form.improvement_suggestions} />
      </div>
    </div>
  );
}

export default SEOEditor;
