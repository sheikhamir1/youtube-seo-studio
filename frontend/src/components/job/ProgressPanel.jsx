import { AlertTriangle, Clock, Cpu, Layers, Zap } from 'lucide-react';

import { formatDuration } from '../../utils/format';
import KeyValue from '../ui/KeyValue';
import ProgressBar from '../ui/ProgressBar';
import { statusLabel } from '../ui/StatusBadge';

/** Overall progress, stage, chunk counter and timing for one job. */
export function ProgressPanel({ job, lastProgress, connected }) {
  if (!job) return null;

  const progress = lastProgress?.progress_percent ?? job.progress_percent ?? 0;
  const status = lastProgress?.status || job.status;
  const stage = lastProgress?.stage || job.stage;
  const currentChunk = lastProgress?.current_chunk ?? job.current_chunk_index;
  const totalChunks = lastProgress?.total_chunks ?? job.total_chunks;
  const isActive = !['COMPLETED', 'FAILED', 'CANCELED'].includes(status);

  const startedAt = job.started_at ? new Date(job.started_at).getTime() : null;
  const finishedAt = job.completed_at || job.failed_at;
  const elapsedSeconds = startedAt
    ? Math.max(0, ((finishedAt ? new Date(finishedAt).getTime() : Date.now()) - startedAt) / 1000)
    : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-sm text-muted">
            {statusLabel(status)} · <span className="text-content">{stage}</span>
          </p>
          {connected && isActive && (
            <p className="mt-0.5 text-xs text-success">Live updates connected</p>
          )}
          {!connected && isActive && (
            <p className="mt-0.5 text-xs text-warning">Reconnecting to the live update stream…</p>
          )}
        </div>
        <p className="mono text-2xl font-semibold tabular-nums">{Number(progress).toFixed(1)}%</p>
      </div>

      <ProgressBar
        value={progress}
        variant={status === 'FAILED' ? 'danger' : status === 'CANCELED' ? 'warning' : 'accent'}
        height="lg"
        animated={isActive}
        label="Overall pipeline progress"
      />

      <KeyValue
        columns={2}
        items={[
          { label: 'Chunks', value: totalChunks ? `${currentChunk !== null && currentChunk !== undefined ? currentChunk + 1 : '—'} / ${totalChunks}` : '—', mono: true, icon: Layers },
          { label: 'Elapsed', value: elapsedSeconds !== null ? formatDuration(elapsedSeconds) : '—', mono: true },
          { label: 'Attempt', value: `${job.attempt_count} ${job.attempt_count === 1 ? 'attempt' : 'attempts'}`, mono: true },
          { label: 'Model', value: job.selected_model, mono: true },
        ]}
      />

      {job.cancel_requested && status !== 'CANCELED' && (
        <p className="flex items-center gap-2 text-xs text-warning">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          Cancellation requested - the worker stops at the next safe point.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5" aria-hidden="true" />
          1 Gemini request at a time (rate-limit safe)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" aria-hidden="true" />
          Long videos take a long time - progress is saved per chunk
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Zap className="h-3.5 w-3.5" aria-hidden="true" />
          Chunk completions are durable: a crash resumes, never restarts from zero
        </span>
      </div>
    </div>
  );
}

export default ProgressPanel;
