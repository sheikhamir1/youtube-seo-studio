import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ROUTES } from '../../constants';
import { cn } from '../../utils/cn';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { SkeletonText } from '../ui/Skeleton';

const Indicator = ({ ok, label, detail }) => (
  <li className="flex items-start justify-between gap-3 py-1.5">
    <span className="flex items-center gap-2 text-sm">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden="true" />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
      )}
      {label}
    </span>
    <span className={cn('text-right text-xs', ok ? 'text-muted' : 'text-danger')}>{detail}</span>
  </li>
);

/** Backend, database, FFmpeg and Gemini-key readiness at a glance. */
export function SystemHealthCard({ status, isLoading, error }) {
  return (
    <Card>
      <CardHeader
        title="System readiness"
        description="Everything runs locally except the Gemini calls."
        actions={
          <Link to={ROUTES.settings}>
            <Button variant="ghost" size="xs">
              Manage
            </Button>
          </Link>
        }
      />
      <CardBody className="pt-1">
        {isLoading && <SkeletonText lines={4} />}

        {!isLoading && error && (
          <div className="flex items-start gap-2 text-sm text-danger">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <p>Backend unreachable.</p>
              <p className="mt-0.5 text-xs text-muted">
                Start the API with <code className="mono">uvicorn app.main:app</code> or{' '}
                <code className="mono">docker compose up</code>.
              </p>
            </div>
          </div>
        )}

        {!isLoading && status && (
          <>
            <ul className="divide-y divide-border/60">
              <Indicator
                ok={status.database?.ok}
                label="PostgreSQL"
                detail={status.database?.ok ? 'connected' : status.database?.detail || 'unavailable'}
              />
              <Indicator
                ok={status.ffmpeg?.ok}
                label="FFmpeg"
                detail={status.ffmpeg?.ok ? 'available' : status.ffmpeg?.detail || 'not found on PATH'}
              />
              <Indicator
                ok={status.ffprobe?.ok}
                label="FFprobe"
                detail={status.ffprobe?.ok ? 'available' : status.ffprobe?.detail || 'not found on PATH'}
              />
              <Indicator
                ok={status.gemini_key_configured}
                label="Gemini API key"
                detail={status.gemini_key_configured ? 'configured' : 'missing GEMINI_API_KEY'}
              />
            </ul>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
              <Badge variant="neutral" mono>
                provider: {status.ai_provider}
              </Badge>
              <Badge variant="neutral" mono>
                model: {status.default_model}
              </Badge>
              <Badge variant="neutral" mono>
                env: {status.app_env}
              </Badge>
              <Badge variant={status.worker?.alive ? 'success' : 'warning'}>
                worker {status.worker?.alive ? 'alive' : 'not running'}
              </Badge>
            </div>

            {status.worker?.current_job_id && (
              <p className="mono mt-2 text-xs text-muted">
                Processing job {status.worker.current_job_id.slice(0, 8)} · {status.worker.current_stage}
              </p>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

export default SystemHealthCard;
