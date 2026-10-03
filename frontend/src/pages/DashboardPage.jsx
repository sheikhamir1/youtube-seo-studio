import { Activity, ListChecks, PlusCircle, Timer } from 'lucide-react';
import { Link } from 'react-router-dom';

import PageHeader from '../components/ui/PageHeader';
import RecentJobs from '../components/dashboard/RecentJobs';
import SystemHealthCard from '../components/dashboard/SystemHealthCard';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import StatCard from '../components/ui/StatCard';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { useJobsQuery } from '../queries/jobs';
import { useQuotaQuery, useSystemStatusQuery } from '../queries/system';
import { formatDuration, formatNumber } from '../utils/format';

const PROCESSING_STATUSES = ['QUEUED', 'VALIDATING', 'EXTRACTING', 'CHUNKING', 'MAPPING', 'REDUCING', 'CANCEL_REQUESTED'];

/** Landing page: what the system is doing right now and what to do next. */
export function DashboardPage() {
  usePageTitle('Dashboard');

  const jobsQuery = useJobsQuery({ page: 1, pageSize: 6 });
  const statusQuery = useSystemStatusQuery();
  const quotaQuery = useQuotaQuery();

  const jobs = jobsQuery.data?.items || [];
  const total = jobsQuery.data?.total || 0;
  const processing = jobs.filter((job) => PROCESSING_STATUSES.includes(job.status)).length;
  const completed = jobs.filter((job) => job.status === 'COMPLETED');
  const scored = completed.filter((job) => typeof job.current_seo_score === 'number');
  const averageScore = scored.length
    ? Math.round(scored.reduce((sum, job) => sum + job.current_seo_score, 0) / scored.length)
    : null;
  const totalDuration = completed.reduce((sum, job) => sum + (job.video_duration_seconds || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="Local-first SEO generation for long-form video. The video never leaves your machine - only extracted audio chunks are sent to Gemini, one at a time."
        actions={
          <Link to={ROUTES.newAnalysis}>
            <Button variant="primary" icon={PlusCircle}>
              New analysis
            </Button>
          </Link>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Analyses"
          value={formatNumber(total)}
          hint="All time"
          icon={ListChecks}
        />
        <StatCard
          label="Processing"
          value={formatNumber(statusQuery.data?.active_jobs ?? processing)}
          hint={statusQuery.data ? `${statusQuery.data.queued_jobs} queued` : 'Live count'}
          icon={Activity}
          variant={processing ? 'accent' : 'default'}
        />
        <StatCard
          label="Video processed"
          value={formatDuration(totalDuration)}
          hint="Completed analyses only"
          icon={Timer}
        />
        <StatCard
          label="Average SEO score"
          value={averageScore !== null ? `${averageScore}` : '—'}
          hint={scored.length ? `Across ${scored.length} result${scored.length === 1 ? '' : 's'}` : 'No results yet'}
          variant={averageScore !== null && averageScore >= 70 ? 'success' : 'default'}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader
            title="Recent analyses"
            description="Newest first."
            actions={
              <Link to={ROUTES.history}>
                <Button variant="ghost" size="xs">
                  View all
                </Button>
              </Link>
            }
          />
          <CardBody className="pt-1">
            <RecentJobs jobs={jobs} isLoading={jobsQuery.isLoading} limit={6} />
          </CardBody>
        </Card>

        <div className="space-y-4">
          <SystemHealthCard
            status={statusQuery.data}
            isLoading={statusQuery.isLoading}
            error={statusQuery.isError}
          />

          <Card>
            <CardHeader title="Gemini pacing" description="Application-tracked usage." />
            <CardBody className="space-y-1.5 text-sm">
              {quotaQuery.isLoading && <p className="text-muted">Loading…</p>}
              {quotaQuery.data && (
                <>
                  <p className="flex items-baseline justify-between">
                    <span className="text-muted">Requests today</span>
                    <span className="mono">
                      {formatNumber(quotaQuery.data.requests_today)} / {formatNumber(quotaQuery.data.rpd_limit)}
                    </span>
                  </p>
                  <p className="flex items-baseline justify-between">
                    <span className="text-muted">Last minute</span>
                    <span className="mono">
                      {quotaQuery.data.rolling_minute_requests} req ·{' '}
                      {formatNumber(quotaQuery.data.rolling_minute_tokens)} tokens
                    </span>
                  </p>
                  <p className="flex items-baseline justify-between">
                    <span className="text-muted">Min interval</span>
                    <span className="mono">{quotaQuery.data.min_interval_seconds}s</span>
                  </p>
                  {quotaQuery.data.estimated_next_request_tokens ? (
                    <p className="flex items-baseline justify-between">
                      <span className="text-muted">Next request ≈</span>
                      <span className="mono">
                        {formatNumber(quotaQuery.data.estimated_next_request_tokens)} tokens
                      </span>
                    </p>
                  ) : null}
                </>
              )}
              {quotaQuery.isError && (
                <p className="text-xs text-danger">Usage data unavailable.</p>
              )}
              <p className="pt-1 text-xs text-muted">
                The worker sends exactly one Gemini request at a time and waits between calls, so rate
                limits slow processing instead of breaking it.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default DashboardPage;
