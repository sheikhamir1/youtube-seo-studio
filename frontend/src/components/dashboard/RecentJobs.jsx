import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ROUTES } from '../../constants';
import { formatRelative, truncate } from '../../utils/format';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';
import { SkeletonTable } from '../ui/Skeleton';
import StatusBadge from '../ui/StatusBadge';

/** Compact list of the newest analyses, linking into the detail view. */
export function RecentJobs({ jobs = [], isLoading = false, limit = 5 }) {
  if (isLoading) return <SkeletonTable rows={limit} columns={3} />;

  if (!jobs.length) {
    return (
      <EmptyState
        compact
        icon={ArrowRight}
        title="No analyses yet"
        description="Start your first analysis: pick a video, optionally add SEO context, and let the pipeline run."
        action={
          <Link to={ROUTES.newAnalysis}>
            <Button variant="primary" size="sm">
              New analysis
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <ul className="divide-y divide-border">
      {jobs.slice(0, limit).map((job) => (
        <li key={job.id}>
          <Link
            to={ROUTES.job(job.id)}
            className="flex items-start justify-between gap-3 py-2.5 transition-colors hover:bg-surface-2"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium" title={job.original_filename}>
                {truncate(job.original_filename, 52)}
              </p>
              <p className="mono mt-0.5 text-xs text-muted">
                {formatRelative(job.created_at)} · {job.selected_model}
                {job.total_chunks ? ` · ${job.total_chunks} chunks` : ''}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {job.current_seo_score !== null && job.current_seo_score !== undefined && (
                <span className="mono text-xs text-muted">score {job.current_seo_score}</span>
              )}
              <StatusBadge status={job.status} />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default RecentJobs;
