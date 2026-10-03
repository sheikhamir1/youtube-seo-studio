import { History, RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { useRestoreResultMutation } from '../../queries/results';
import { useToastStore } from '../../stores/toastStore';
import { describeApiError } from '../../utils/errors';
import { formatDateTime, truncate } from '../../utils/format';
import { Badge } from '../ui/Badge';
import Button from '../ui/Button';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import EmptyState from '../ui/EmptyState';

/**
 * Every Reduce run creates a new immutable version. Restoring an older version
 * makes it current without deleting the newer one.
 */
export function VersionHistory({ jobId, results = [], currentId }) {
  const [restoreTarget, setRestoreTarget] = useState(null);
  const restoreMutation = useRestoreResultMutation(jobId);
  const pushToast = useToastStore((state) => state.push);

  const runRestore = async () => {
    try {
      await restoreMutation.mutateAsync(restoreTarget.id);
      pushToast({
        variant: 'success',
        title: `Version ${restoreTarget.version_number} is current`,
        description: 'Later versions are kept and can be restored again.',
      });
      setRestoreTarget(null);
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  if (!results.length) {
    return (
      <EmptyState
        compact
        title="No versions yet"
        description="Generated SEO results appear here; each regeneration adds a new version."
      />
    );
  }

  return (
    <>
      <ul className="space-y-2">
        {results.map((result) => {
          const isCurrent = result.id === currentId || result.is_current;
          return (
            <li
              key={result.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-border p-3"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">Version {result.version_number}</span>
                  {isCurrent && <Badge variant="success">Current</Badge>}
                  {result.edited_by_user && <Badge variant="accent">Edited</Badge>}
                  <Badge variant="neutral" mono>
                    score {result.seo_score}
                  </Badge>
                </div>
                <p className="mt-1 truncate text-sm text-muted" title={result.title}>
                  {truncate(result.title, 90)}
                </p>
                <p className="mono mt-0.5 text-xs text-muted">
                  {formatDateTime(result.created_at)} · {result.model}
                  {result.prompt_template_name_snapshot
                    ? ` · ${result.prompt_template_name_snapshot}`
                    : ''}
                </p>
              </div>
              {!isCurrent && (
                <Button
                  variant="outline"
                  size="sm"
                  icon={RotateCcw}
                  onClick={() => setRestoreTarget(result)}
                >
                  Make current
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      <ConfirmDialog
        isOpen={Boolean(restoreTarget)}
        onClose={() => setRestoreTarget(null)}
        onConfirm={runRestore}
        title={`Make version ${restoreTarget?.version_number} current?`}
        message="This version becomes the result shown and copied by default. Other versions stay available."
        confirmLabel="Make current"
        variant="primary"
        isLoading={restoreMutation.isPending}
      />
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
        <History className="h-3.5 w-3.5" aria-hidden="true" />
        Versions are immutable snapshots of a Reduce run.
      </p>
    </>
  );
}

export default VersionHistory;
