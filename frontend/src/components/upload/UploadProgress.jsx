import { Pause, Play, X } from 'lucide-react';

import { formatBytes, formatDuration } from '../../utils/format';
import Button from '../ui/Button';
import ProgressBar from '../ui/ProgressBar';

/**
 * Live upload progress: real bytes, real speed, real ETA, plus working
 * pause / resume / cancel controls.
 */
export function UploadProgress({
  progress,
  onPause,
  onResume,
  onCancel,
  onRetry,
  isPaused = false,
}) {
  const {
    filename,
    sizeBytes = 0,
    uploadedBytes = 0,
    percent = 0,
    bytesPerSecond = 0,
    etaSeconds = null,
    nextPart = 0,
    totalParts = 0,
    status,
    error,
  } = progress || {};

  const failed = status === 'failed';
  const canceled = status === 'canceled';

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{filename || 'Uploading…'}</p>
          <p className="mono text-xs text-muted">
            {formatBytes(uploadedBytes)} / {formatBytes(sizeBytes)} · part {Math.min(nextPart + 1, totalParts || 1)} of{' '}
            {totalParts || '?'}
          </p>
        </div>
        <span className="mono text-lg font-semibold tabular-nums">{percent.toFixed(1)}%</span>
      </div>

      <ProgressBar
        value={percent}
        variant={failed ? 'danger' : canceled ? 'warning' : 'accent'}
        className="mt-3"
        label={`Upload progress ${percent.toFixed(0)} percent`}
      />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span className="mono">
          {bytesPerSecond > 0 ? `${formatBytes(bytesPerSecond)}/s` : 'measuring speed…'}
          {etaSeconds !== null && etaSeconds !== undefined
            ? ` · ${formatDuration(etaSeconds)} remaining`
            : ''}
        </span>
        <div className="flex items-center gap-1.5">
          {!failed && !canceled && !isPaused && status === 'uploading' && (
            <Button variant="outline" size="xs" icon={Pause} onClick={onPause}>
              Pause
            </Button>
          )}
          {isPaused && (
            <Button variant="outline" size="xs" icon={Play} onClick={onResume}>
              Resume
            </Button>
          )}
          {failed && onRetry && (
            <Button variant="outline" size="xs" icon={Play} onClick={onRetry}>
              Retry
            </Button>
          )}
          {!canceled && (
            <Button variant="ghost" size="xs" icon={X} onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export default UploadProgress;
