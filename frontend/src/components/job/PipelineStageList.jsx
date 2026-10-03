import { Check, Loader2, X } from 'lucide-react';

import { JOB_STATUS } from '../../constants';
import { cn } from '../../utils/cn';

/**
 * The six pipeline stages with their real state.
 *
 * A stage is `done` only when the backend reported it completed or a later
 * stage is already running; the current stage is the one the job's status
 * points at. Nothing here invents progress the backend did not report.
 */
const STAGE_ORDER = [
  { key: 'VALIDATION', label: 'Validation', status: JOB_STATUS.VALIDATING, detail: 'FFprobe metadata + audio stream check' },
  { key: 'EXTRACTION', label: 'Audio extraction', status: JOB_STATUS.EXTRACTING, detail: 'FFmpeg → FLAC 16 kHz mono' },
  { key: 'CHUNKING', label: 'Chunking', status: JOB_STATUS.CHUNKING, detail: '60-minute windows with 60 s overlap' },
  { key: 'MAPPING', label: 'AI mapping', status: JOB_STATUS.MAPPING, detail: 'One Gemini call per chunk, sequential' },
  { key: 'REDUCTION', label: 'SEO generation', status: JOB_STATUS.REDUCING, detail: 'Single Reduce call over the merged timeline' },
];

export function PipelineStageList({ job }) {
  if (!job) return null;

  const statusIndex = STAGE_ORDER.findIndex((stage) => stage.status === job.status);
  const isCompleted = job.status === JOB_STATUS.COMPLETED;
  const isFailed = job.status === JOB_STATUS.FAILED;
  const isCanceled = job.status === JOB_STATUS.CANCELED;
  const failedStage = job.failed_stage;
  const activeIndex = statusIndex;

  return (
    <ol className="space-y-0">
      {STAGE_ORDER.map((stage, index) => {
        const stageFailed = isFailed && failedStage === stage.key;
        const done =
          (isCompleted && true) ||
          activeIndex > index ||
          (activeIndex === -1 && !isFailed && !isCanceled && job.progress_percent >= 100);
        const active = activeIndex === index && !isFailed && !isCanceled;
        const stageCanceled = isCanceled && (activeIndex === index || activeIndex === -1);

        return (
          <li key={stage.key} className="relative flex gap-3 pb-4 last:pb-0">
            {index < STAGE_ORDER.length - 1 && (
              <span
                className={cn(
                  'absolute left-[11px] top-6 h-[calc(100%-1.5rem)] w-px',
                  done ? 'bg-success/40' : 'bg-border',
                )}
                aria-hidden="true"
              />
            )}
            <span
              className={cn(
                'relative z-10 mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold',
                stageFailed
                  ? 'border-danger/50 bg-danger/15 text-danger'
                  : done
                    ? 'border-success/40 bg-success/15 text-success'
                    : active
                      ? 'border-accent/50 bg-accent/15 text-accent'
                      : 'border-border bg-surface-2 text-muted',
              )}
              aria-hidden="true"
            >
              {stageFailed ? (
                <X className="h-3 w-3" />
              ) : done ? (
                <Check className="h-3 w-3" />
              ) : active ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                index + 1
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  'text-sm font-medium',
                  active ? 'text-content' : done ? 'text-content' : 'text-muted',
                  stageCanceled && 'line-through decoration-muted',
                )}
              >
                {stage.label}
                {stageFailed && <span className="ml-2 text-xs font-normal text-danger">failed here</span>}
              </p>
              <p className="mt-0.5 text-xs text-muted">{stage.detail}</p>
              {stage.key === 'MAPPING' && job.total_chunks ? (
                <p className="mono mt-0.5 text-xs text-muted">
                  {job.current_chunk_index !== null && job.current_chunk_index !== undefined
                    ? `chunk ${job.current_chunk_index + 1} of ${job.total_chunks}`
                    : `${job.total_chunks} chunks queued`}
                </p>
              ) : null}
              {stageFailed && job.current_error_message ? (
                <p className="mt-0.5 text-xs text-danger">{job.current_error_message}</p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export const PIPELINE_STAGE_ORDER = STAGE_ORDER;
export default PipelineStageList;
