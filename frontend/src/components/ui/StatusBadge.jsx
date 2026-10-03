import { JOB_STATUS } from '../../constants';
import { cn } from '../../utils/cn';

/** Single source of truth for how each job status is presented. */
const STATUS_META = {
  [JOB_STATUS.QUEUED]: { label: 'Queued', className: 'bg-surface-2 text-muted border-border' },
  [JOB_STATUS.VALIDATING]: { label: 'Validating', className: 'bg-accent/12 text-accent border-accent/30' },
  [JOB_STATUS.EXTRACTING]: { label: 'Extracting audio', className: 'bg-accent/12 text-accent border-accent/30' },
  [JOB_STATUS.CHUNKING]: { label: 'Chunking', className: 'bg-accent/12 text-accent border-accent/30' },
  [JOB_STATUS.MAPPING]: { label: 'AI mapping', className: 'bg-accent/12 text-accent border-accent/30' },
  [JOB_STATUS.REDUCING]: { label: 'Generating SEO', className: 'bg-accent/12 text-accent border-accent/30' },
  [JOB_STATUS.COMPLETED]: { label: 'Completed', className: 'bg-success/12 text-success border-success/30' },
  [JOB_STATUS.FAILED]: { label: 'Failed', className: 'bg-danger/12 text-danger border-danger/40' },
  [JOB_STATUS.CANCEL_REQUESTED]: {
    label: 'Cancelling',
    className: 'bg-warning/12 text-warning border-warning/30',
  },
  [JOB_STATUS.CANCELED]: { label: 'Canceled', className: 'bg-surface-2 text-muted border-border' },
};

export const statusLabel = (status) => STATUS_META[status]?.label || status || 'Unknown';

export function StatusBadge({ status, className, withDot = true }) {
  const meta = STATUS_META[status] || {
    label: status || 'Unknown',
    className: 'bg-surface-2 text-muted border-border',
  };
  const animated = [
    JOB_STATUS.VALIDATING,
    JOB_STATUS.EXTRACTING,
    JOB_STATUS.CHUNKING,
    JOB_STATUS.MAPPING,
    JOB_STATUS.REDUCING,
  ].includes(status);

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium',
        meta.className,
        className,
      )}
    >
      {withDot && (
        <span
          className={cn('h-1.5 w-1.5 rounded-full bg-current', animated && 'animate-pulse')}
          aria-hidden="true"
        />
      )}
      {meta.label}
    </span>
  );
}

export default StatusBadge;
