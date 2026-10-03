import { Plus, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import TemplateCard from '../components/templates/TemplateCard';
import Button from '../components/ui/Button';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';
import EmptyState from '../components/ui/EmptyState';
import Input from '../components/ui/Input';
import PageHeader from '../components/ui/PageHeader';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import {
  useDeleteTemplateMutation,
  useDuplicateTemplateMutation,
  useTemplatesQuery,
} from '../queries/templates';
import { useToastStore } from '../stores/toastStore';
import { describeApiError } from '../utils/errors';

/** Template library: list, search, duplicate and delete. */
export function PromptTemplatesPage() {
  usePageTitle('Prompt templates');

  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const templatesQuery = useTemplatesQuery();
  const duplicateMutation = useDuplicateTemplateMutation();
  const deleteMutation = useDeleteTemplateMutation();
  const pushToast = useToastStore((state) => state.push);

  const templates = useMemo(() => templatesQuery.data?.items || [], [templatesQuery.data]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return templates;
    return templates.filter(
      (template) =>
        template.name.toLowerCase().includes(needle) ||
        (template.description || '').toLowerCase().includes(needle) ||
        template.user_prompt_template.toLowerCase().includes(needle),
    );
  }, [templates, search]);

  const duplicate = async (template) => {
    try {
      await duplicateMutation.mutateAsync(template.id);
      pushToast({ variant: 'success', title: 'Template duplicated' });
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  const remove = async () => {
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      pushToast({ variant: 'success', title: 'Template deleted' });
      setDeleteTarget(null);
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Prompt templates"
        description="The Reduce prompt is fully editable. Only this phase is customizable - Map prompts are fixed so chunk analysis stays consistent."
        actions={
          <Link to={ROUTES.newPromptTemplate}>
            <Button variant="primary" icon={Plus}>
              New template
            </Button>
          </Link>
        }
      />

      <div className="max-w-md">
        <Input
          placeholder="Search templates…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          leftAddon={<Search className="h-3.5 w-3.5" />}
          aria-label="Search templates"
        />
      </div>

      {templatesQuery.isLoading && <p className="text-sm text-muted">Loading templates…</p>}

      {templatesQuery.isError && (
        <EmptyState
          title="Templates unavailable"
          description="The backend could not be reached, or the template table could not be read."
        />
      )}

      {!templatesQuery.isLoading && !filtered.length && (
        <EmptyState
          title={search ? 'No templates match that search' : 'No templates yet'}
          description={
            search
              ? 'Try a different search term.'
              : 'Create a template to control exactly how the SEO metadata is generated.'
          }
          action={
            search ? (
              <Button variant="outline" onClick={() => setSearch('')}>
                Clear search
              </Button>
            ) : (
              <Link to={ROUTES.newPromptTemplate}>
                <Button variant="primary">New template</Button>
              </Link>
            )
          }
        />
      )}

      <div className="space-y-3">
        {filtered.map((template) => (
          <TemplateCard
            key={template.id}
            template={template}
            onEdit={(selected) => navigate(ROUTES.promptTemplate(selected.id))}
            onDuplicate={duplicate}
            onDelete={setDeleteTarget}
          />
        ))}
      </div>

      <ConfirmDialog
        isOpen={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={remove}
        title={`Delete “${deleteTarget?.name}”?`}
        message="Analyses that already used this template keep their stored word-for-word prompt snapshot."
        confirmLabel="Delete template"
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

export default PromptTemplatesPage;
