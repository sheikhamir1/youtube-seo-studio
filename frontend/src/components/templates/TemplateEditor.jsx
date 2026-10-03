import { Eye, Save, X } from 'lucide-react';
import { useRef, useState } from 'react';

import { usePreviewTemplateMutation } from '../../queries/templates';
import { useToastStore } from '../../stores/toastStore';
import { describeApiError } from '../../utils/errors';
import Alert from '../ui/Alert';
import Button from '../ui/Button';
import { Card, CardBody, CardFooter, CardHeader } from '../ui/Card';
import Input, { Textarea } from '../ui/Input';
import { LoadingBlock } from '../ui/Spinner';
import VariableReference from './VariableReference';

/**
 * Create/edit form for a Reduce prompt template.
 *
 * `user_prompt_template` always renders through the backend's sandboxed Jinja
 * environment, so Preview shows exactly what Gemini would receive.
 */
export function TemplateEditor({
  template = null,
  variables = [],
  sampleContext = null,
  onSave,
  onCancel,
  isSaving = false,
  isLoading = false,
  error = null,
}) {
  const isEdit = Boolean(template);
  const [form, setForm] = useState({
    name: template?.name || '',
    description: template?.description || '',
    system_prompt: template?.system_prompt || '',
    user_prompt_template: template?.user_prompt_template || '',
  });
  const [localError, setLocalError] = useState(null);
  const promptRef = useRef(null);
  const previewMutation = usePreviewTemplateMutation();
  const pushToast = useToastStore((state) => state.push);

  const update = (field, value) => {
    setForm((previous) => ({ ...previous, [field]: value }));
    setLocalError(null);
  };

  const insertVariable = (variable) => {
    const token = `{{ ${variable} }}`;
    const element = promptRef.current;
    if (!element) {
      update('user_prompt_template', `${form.user_prompt_template}${token}`);
      return;
    }
    const start = element.selectionStart ?? form.user_prompt_template.length;
    const end = element.selectionEnd ?? start;
    const next = `${form.user_prompt_template.slice(0, start)}${token}${form.user_prompt_template.slice(end)}`;
    update('user_prompt_template', next);
    requestAnimationFrame(() => {
      element.focus();
      element.setSelectionRange(start + token.length, start + token.length);
    });
  };

  const runPreview = async () => {
    try {
      const preview = await previewMutation.mutateAsync({
        userPromptTemplate: form.user_prompt_template,
        sampleContext,
      });
      return preview;
    } catch (previewError) {
      const { title, detail } = describeApiError(previewError);
      pushToast({ variant: 'error', title, description: detail });
      return null;
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setLocalError('Template name is required.');
      return;
    }
    if (!form.system_prompt.trim()) {
      setLocalError('The system prompt is required.');
      return;
    }
    if (!form.user_prompt_template.trim()) {
      setLocalError('The user prompt template is required.');
      return;
    }
    setLocalError(null);
    try {
      await onSave?.(form);
    } catch (saveError) {
      const { title, detail } = describeApiError(saveError);
      setLocalError([title, detail].filter(Boolean).join(' '));
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <LoadingBlock label="Loading template…" />
        </CardBody>
      </Card>
    );
  }

  const previewText = previewMutation.data?.rendered_prompt;
  const usedVariables = previewMutation.data?.used_variables || [];

  return (
    <form onSubmit={submit} className="space-y-4">
      <Card>
        <CardHeader
          title={isEdit ? `Edit template: ${template.name}` : 'New prompt template'}
          description="This text becomes the Reduce prompt. Map-phase prompts are fixed and not editable."
          actions={
            <>
              <Button variant="ghost" size="sm" icon={X} onClick={onCancel} type="button">
                Cancel
              </Button>
              <Button variant="primary" size="sm" icon={Save} type="submit" isLoading={isSaving}>
                {isEdit ? 'Save template' : 'Create template'}
              </Button>
            </>
          }
        />
        <CardBody className="space-y-4">
          {(localError || error) && (
            <Alert variant="error" title="Template not saved">
              {localError || describeApiError(error).title}
            </Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Name"
              value={form.name}
              onChange={(event) => update('name', event.target.value)}
              maxLength={200}
              required
              hint="Shown when choosing a template for an analysis."
            />
            <Input
              label="Description (optional)"
              value={form.description}
              onChange={(event) => update('description', event.target.value)}
              maxLength={1000}
            />
          </div>

          <Textarea
            label="System prompt"
            value={form.system_prompt}
            onChange={(event) => update('system_prompt', event.target.value)}
            className="min-h-[140px] font-mono text-[13px]"
            hint="Sets the model's role and the hard rules it must follow."
          />

          <Textarea
            ref={promptRef}
            label="User prompt template"
            value={form.user_prompt_template}
            onChange={(event) => update('user_prompt_template', event.target.value)}
            className="min-h-[320px] font-mono text-[13px]"
            hint="Use {{ variable }} placeholders. Everything else is sent verbatim."
          />

          {usedVariables.length > 0 && (
            <p className="mono text-xs text-muted">
              Uses: {usedVariables.map((variable) => `{{ ${variable} }}`).join(', ')}
            </p>
          )}
        </CardBody>
        <CardFooter>
          <p className="text-xs text-muted">
            Only the Reduce phase is customizable: it receives the merged timeline, never audio.
          </p>
          <Button
            variant="outline"
            size="sm"
            type="button"
            icon={Eye}
            isLoading={previewMutation.isPending}
            onClick={runPreview}
            disabled={!form.user_prompt_template.trim()}
          >
            Preview render
          </Button>
        </CardFooter>
      </Card>

      {previewText && (
        <Card>
          <CardHeader
            title="Rendered prompt (sample data)"
            description="Exactly what would be sent, with the sample context substituted. No AI call is made."
          />
          <CardBody>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-surface-2 p-3 text-[13px] scrollbar-thin">
              {previewText}
            </pre>
          </CardBody>
        </Card>
      )}

      <VariableReference variables={variables} sampleContext={sampleContext} onInsert={insertVariable} />
    </form>
  );
}

export default TemplateEditor;
