import { ExternalLink, RotateCcw, Square, Trash2, Wand2 } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { isActiveStatus, ROUTES } from '../../constants';
import { useCancelJobMutation, useDeleteJobMutation, useRetryJobMutation } from '../../queries/jobs';
import { useToastStore } from '../../stores/toastStore';
import { describeApiError } from '../../utils/errors';
import Button from '../ui/Button';
import { ConfirmDialog } from '../ui/ConfirmDialog';

/**
 * Status-aware job actions. Every button performs a real backend call; buttons
 * that cannot apply to the current state are not rendered at all.
 */
export function JobActions({ job, onDeleted, onRegenerate, compact = false }) {
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const pushToast = useToastStore((state) => state.push);

  const cancelMutation = useCancelJobMutation(job?.id);
  const retryMutation = useRetryJobMutation(job?.id);
  const deleteMutation = useDeleteJobMutation();

  if (!job) return null;

  const active = isActiveStatus(job.status);

  const runCancel = async () => {
    try {
      await cancelMutation.mutateAsync();
      pushToast({
        variant: 'info',
        title: 'Cancellation requested',
        description: 'The worker stops at the next safe point and keeps finished chunks.',
      });
      setConfirmCancel(false);
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  const runRetry = async () => {
    try {
      await retryMutation.mutateAsync();
      pushToast({
        variant: 'success',
        title: 'Job re-queued',
        description: 'Processing resumes from the first unfinished chunk.',
      });
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  const runDelete = async () => {
    try {
      await deleteMutation.mutateAsync(job.id);
      pushToast({ variant: 'success', title: 'Analysis deleted' });
      setConfirmDelete(false);
      onDeleted?.();
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        {active && (
          <Button
            variant="danger"
            size={compact ? 'sm' : 'md'}
            icon={Square}
            isLoading={cancelMutation.isPending}
            onClick={() => setConfirmCancel(true)}
          >
            Cancel
          </Button>
        )}
        {['FAILED', 'CANCELED'].includes(job.status) && (
          <Button
            variant="primary"
            size={compact ? 'sm' : 'md'}
            icon={RotateCcw}
            isLoading={retryMutation.isPending}
            onClick={runRetry}
          >
            Retry
          </Button>
        )}
        {job.status === 'COMPLETED' && (
          <>
            {onRegenerate && (
              <Button
                variant="secondary"
                size={compact ? 'sm' : 'md'}
                icon={Wand2}
                onClick={() => onRegenerate()}
              >
                Regenerate SEO
              </Button>
            )}
            {!compact && (
              <Link to={ROUTES.timeline(job.id)}>
                <Button variant="outline" size="md" icon={ExternalLink}>
                  Timeline
                </Button>
              </Link>
            )}
          </>
        )}
        <Button
          variant="ghost"
          size={compact ? 'sm' : 'md'}
          icon={Trash2}
          onClick={() => setConfirmDelete(true)}
        >
          Delete
        </Button>
      </div>

      <ConfirmDialog
        isOpen={confirmCancel}
        onClose={() => setConfirmCancel(false)}
        onConfirm={runCancel}
        title="Cancel this analysis?"
        message="Finished chunks are kept, and the analysis can be retried later without re-processing them."
        confirmLabel="Cancel analysis"
        cancelLabel="Keep running"
        isLoading={cancelMutation.isPending}
      />
      <ConfirmDialog
        isOpen={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={runDelete}
        title="Delete this analysis?"
        message="The extracted audio, chunks, generated SEO and all versions are removed from local storage. This cannot be undone."
        confirmLabel="Delete permanently"
        isLoading={deleteMutation.isPending}
      />
    </>
  );
}

export default JobActions;
