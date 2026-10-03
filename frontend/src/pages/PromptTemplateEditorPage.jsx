import { useNavigate, useParams } from 'react-router-dom';

import TemplateEditor from '../components/templates/TemplateEditor';
import PageHeader from '../components/ui/PageHeader';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import {
  useCreateTemplateMutation,
  useTemplateQuery,
  useTemplateVariablesQuery,
  useUpdateTemplateMutation,
} from '../queries/templates';
import { useToastStore } from '../stores/toastStore';

/**
 * Handles both `/prompt-templates/new` and `/prompt-templates/:templateId`:
 * the same editor, with or without an existing template.
 */
export function PromptTemplateEditorPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(templateId);
  const pushToast = useToastStore((state) => state.push);

  const templateQuery = useTemplateQuery(templateId);
  const variablesQuery = useTemplateVariablesQuery();
  const createMutation = useCreateTemplateMutation();
  const updateMutation = useUpdateTemplateMutation();

  usePageTitle(isEdit ? 'Edit template' : 'New template');

  const save = async (form) => {
    const payload = {
      name: form.name,
      description: form.description || null,
      system_prompt: form.system_prompt,
      user_prompt_template: form.user_prompt_template,
    };
    if (isEdit) {
      await updateMutation.mutateAsync({ templateId, payload });
      pushToast({ variant: 'success', title: 'Template saved' });
      navigate(ROUTES.promptTemplates);
      return;
    }
    const response = await createMutation.mutateAsync(payload);
    pushToast({ variant: 'success', title: 'Template created' });
    navigate(ROUTES.promptTemplate(response.data.id));
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={isEdit ? 'Edit template' : 'New prompt template'}
        description="The template defines the Reduce prompt that turns the merged timeline into validated SEO metadata."
        backTo={ROUTES.promptTemplates}
        backLabel="Templates"
      />

      <TemplateEditor
        template={isEdit ? templateQuery.data : null}
        variables={variablesQuery.data?.available_variables || []}
        sampleContext={variablesQuery.data?.sample_context || null}
        onSave={save}
        onCancel={() => navigate(ROUTES.promptTemplates)}
        isSaving={createMutation.isPending || updateMutation.isPending}
        isLoading={isEdit && templateQuery.isLoading}
        error={isEdit ? templateQuery.error : null}
      />
    </div>
  );
}

export default PromptTemplateEditorPage;
