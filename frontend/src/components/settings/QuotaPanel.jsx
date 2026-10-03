import { AlertTriangle, Gauge } from 'lucide-react';

import { formatNumber } from '../../utils/format';
import Alert from '../ui/Alert';
import { Card, CardBody, CardHeader } from '../ui/Card';
import ProgressBar from '../ui/ProgressBar';
import { LoadingBlock } from '../ui/Spinner';

/**
 * Application-tracked Gemini usage: what this app has sent today, paced by the
 * configured limits. It is explicitly not a claim about Google's own quota.
 */
export function QuotaPanel({ quota, isLoading }) {
  if (isLoading) return <LoadingBlock label="Loading quota…" />;
  if (!quota) return null;

  const dailyPercent = quota.rpd_limit ? (quota.requests_today / quota.rpd_limit) * 100 : 0;
  const rpmPercent = quota.rpm_limit ? (quota.rolling_minute_requests / quota.rpm_limit) * 100 : 0;
  const tpmPercent = quota.tpm_limit ? (quota.rolling_minute_tokens / quota.tpm_limit) * 100 : 0;

  return (
    <Card>
      <CardHeader
        icon={Gauge}
        title="API usage (tracked locally)"
        description="Requests this application sent, paced by the configured limits."
      />
      <CardBody className="space-y-4">
        {quota.daily_budget_reached && (
          <Alert variant="warning" title="Daily request budget reached">
            Processing pauses until the daily counter resets.
          </Alert>
        )}
        {quota.warning && (
          <Alert variant="warning" title="Heads up">
            {quota.warning}
          </Alert>
        )}

        <div>
          <div className="flex items-baseline justify-between text-sm">
            <span>Requests today</span>
            <span className="mono">
              {formatNumber(quota.requests_today)} / {formatNumber(quota.rpd_limit)}
            </span>
          </div>
          <ProgressBar
            className="mt-1.5"
            value={dailyPercent}
            variant={dailyPercent > 85 ? 'danger' : dailyPercent > 60 ? 'warning' : 'accent'}
            label="Daily requests used"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <div className="flex items-baseline justify-between text-sm">
              <span>Requests / minute</span>
              <span className="mono">
                {quota.rolling_minute_requests} / {quota.rpm_limit}
              </span>
            </div>
            <ProgressBar className="mt-1.5" value={rpmPercent} height="sm" variant="accent" />
          </div>
          <div>
            <div className="flex items-baseline justify-between text-sm">
              <span>Tokens / minute</span>
              <span className="mono">
                {formatNumber(quota.rolling_minute_tokens)} / {formatNumber(quota.tpm_limit)}
              </span>
            </div>
            <ProgressBar className="mt-1.5" value={tpmPercent} height="sm" variant="accent" />
          </div>
        </div>

        <p className="flex items-start gap-1.5 text-xs text-muted">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          Minimum interval between requests: {quota.min_interval_seconds}s. The worker sends exactly
          one Gemini request at a time, so hitting a limit simply slows processing instead of failing
          a job.
        </p>
      </CardBody>
    </Card>
  );
}

export default QuotaPanel;
