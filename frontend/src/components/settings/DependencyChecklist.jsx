import { CheckCircle2, Copy, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ROUTES } from '../../constants';
import { cn } from '../../utils/cn';
import Button from '../ui/Button';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { LoadingBlock } from '../ui/Spinner';

/**
 * Actionable setup checklist. Each failing row says exactly what to run, so a
 * fresh clone can be fixed without reading source code.
 */
const CHECKS = [
  {
    key: 'database',
    label: 'PostgreSQL reachable',
    fix: 'docker compose up -d postgres && alembic upgrade head',
  },
  {
    key: 'ffmpeg',
    label: 'FFmpeg installed',
    fix: 'sudo apt-get install -y ffmpeg   # or: brew install ffmpeg',
  },
  {
    key: 'ffprobe',
    label: 'FFprobe installed',
    fix: 'FFprobe ships with FFmpeg - reinstall FFmpeg if it is missing.',
  },
  {
    key: 'gemini_key_configured',
    label: 'GEMINI_API_KEY configured',
    fix: 'echo "GEMINI_API_KEY=your-key" >> .env   # then restart the backend',
  },
];

export function DependencyChecklist({ status, isLoading }) {
  if (isLoading) return <LoadingBlock label="Checking dependencies…" />;

  const rows = CHECKS.map((check) => {
    const value = status?.[check.key];
    const ok = typeof value === 'object' ? Boolean(value?.ok) : Boolean(value);
    const detail = typeof value === 'object' ? value?.detail : null;
    return { ...check, ok, detail };
  });

  return (
    <Card>
      <CardHeader
        title="Setup checklist"
        description="The pipeline needs FFmpeg, a reachable database and a Gemini key."
        actions={
          <Link to={ROUTES.newAnalysis}>
            <Button variant="ghost" size="xs">
              Start an analysis
            </Button>
          </Link>
        }
      />
      <CardBody className="space-y-3">
        <ul className="space-y-2">
          {rows.map((row) => (
            <li
              key={row.key}
              className={cn(
                'rounded-md border p-3',
                row.ok ? 'border-border' : 'border-danger/40 bg-danger/5',
              )}
            >
              <div className="flex items-center gap-2">
                {row.ok ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                ) : (
                  <XCircle className="h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
                )}
                <span className="text-sm font-medium">{row.label}</span>
              </div>
              {!row.ok && (
                <div className="mt-2 space-y-2">
                  {row.detail && <p className="text-xs text-danger">{row.detail}</p>}
                  <div className="flex items-center gap-2">
                    <code className="mono flex-1 overflow-x-auto rounded border border-border bg-surface-2 px-2 py-1 text-xs">
                      {row.fix}
                    </code>
                    <Button
                      variant="ghost"
                      size="xs"
                      icon={Copy}
                      onClick={() => navigator.clipboard?.writeText(row.fix)}
                    >
                      Copy
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>

        {status && (
          <p className="text-xs text-muted">
            {status.queued_jobs} queued · {status.active_jobs} active · worker{' '}
            {status.worker?.alive ? 'alive' : 'not running'}
            {status.worker?.heartbeat_age_seconds !== null &&
            status.worker?.heartbeat_age_seconds !== undefined
              ? ` (heartbeat ${Math.round(status.worker.heartbeat_age_seconds)}s ago)`
              : ''}
          </p>
        )}
      </CardBody>
    </Card>
  );
}

export default DependencyChecklist;
