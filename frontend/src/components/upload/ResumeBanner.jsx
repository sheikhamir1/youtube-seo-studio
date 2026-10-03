import { RotateCcw, X } from 'lucide-react';

import { formatBytes } from '../../utils/format';
import Button from '../ui/Button';

/**
 * Shown on New Analysis when a previous upload session was interrupted: the
 * user can continue it (nothing is re-uploaded) or discard it.
 */
export function ResumeBanner({ session, onResume, onDiscard, isResuming = false }) {
  if (!session) return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/40 bg-warning/10 p-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">Unfinished upload found</p>
        <p className="mono mt-0.5 text-xs text-muted">
          {session.filename} · {formatBytes(session.receivedSize)} of {formatBytes(session.sizeBytes)}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" icon={X} onClick={onDiscard} disabled={isResuming}>
          Discard
        </Button>
        <Button variant="primary" size="sm" icon={RotateCcw} onClick={onResume} isLoading={isResuming}>
          Resume upload
        </Button>
      </div>
    </div>
  );
}

export default ResumeBanner;
