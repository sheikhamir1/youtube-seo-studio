import { Filter, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import JobActions from '../components/job/JobActions';
import StatusBadge from '../components/ui/StatusBadge';
import Button from '../components/ui/Button';
import { Card, CardBody } from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import Input from '../components/ui/Input';
import PageHeader from '../components/ui/PageHeader';
import Select from '../components/ui/Select';
import { SkeletonTable } from '../components/ui/Skeleton';
import { HISTORY_FILTERS, ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { useJobsQuery } from '../queries/jobs';
import { formatDateTime, formatDuration, formatNumber, truncate } from '../utils/format';

const SORT_OPTIONS = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'created_at', label: 'Oldest first' },
  { value: '-updated_at', label: 'Recently updated' },
  { value: '-video_duration_seconds', label: 'Longest video' },
];

/** Searchable, filterable, paginated analysis history. */
export function HistoryPage() {
  usePageTitle('History');

  const [filters, setFilters] = useState({ status: '', search: '', sort: '-created_at', page: 1 });
  const [searchDraft, setSearchDraft] = useState('');

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((previous) => ({ ...previous, search: searchDraft, page: 1 }));
    }, 350);
    return () => clearTimeout(timer);
  }, [searchDraft]);

  const jobsQuery = useJobsQuery({
    page: filters.page,
    pageSize: 20,
    status: filters.status,
    search: filters.search,
    sort: filters.sort,
  });

  const jobs = jobsQuery.data?.items || [];
  const total = jobsQuery.data?.total || 0;
  const pageSize = jobsQuery.data?.page_size || 20;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasFilters = Boolean(filters.status || filters.search);

  return (
    <div className="space-y-5">
      <PageHeader
        title="History"
        description="Every analysis with its status, duration and current SEO score."
        actions={
          <Link to={ROUTES.newAnalysis}>
            <Button variant="primary">New analysis</Button>
          </Link>
        }
      />

      <Card>
        <CardBody className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-[1fr_180px_180px]">
            <Input
              placeholder="Search by file name…"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              leftAddon={<Search className="h-3.5 w-3.5" />}
              rightAddon={
                searchDraft ? (
                  <button type="button" onClick={() => setSearchDraft('')} aria-label="Clear search">
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null
              }
              aria-label="Search analyses"
            />
            <Select
              options={HISTORY_FILTERS}
              value={filters.status}
              onChange={(event) =>
                setFilters((previous) => ({ ...previous, status: event.target.value, page: 1 }))
              }
              aria-label="Filter by status"
            />
            <Select
              options={SORT_OPTIONS}
              value={filters.sort}
              onChange={(event) =>
                setFilters((previous) => ({ ...previous, sort: event.target.value, page: 1 }))
              }
              aria-label="Sort analyses"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>
              {formatNumber(total)} {total === 1 ? 'analysis' : 'analyses'}
              {hasFilters ? ' matching your filters' : ''}
            </span>
            {hasFilters && (
              <Button
                variant="ghost"
                size="xs"
                icon={Filter}
                onClick={() => {
                  setSearchDraft('');
                  setFilters({ status: '', search: '', sort: '-created_at', page: 1 });
                }}
              >
                Clear filters
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      {jobsQuery.isLoading && (
        <Card>
          <CardBody>
            <SkeletonTable rows={8} columns={5} />
          </CardBody>
        </Card>
      )}

      {!jobsQuery.isLoading && !jobs.length && (
        <EmptyState
          title={hasFilters ? 'No analyses match those filters' : 'No analyses yet'}
          description={
            hasFilters
              ? 'Try a different search term or clear the filters.'
              : 'Upload a long-form video to generate your first set of SEO metadata.'
          }
          action={
            hasFilters ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearchDraft('');
                  setFilters({ status: '', search: '', sort: '-created_at', page: 1 });
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Link to={ROUTES.newAnalysis}>
                <Button variant="primary">New analysis</Button>
              </Link>
            )
          }
        />
      )}

      {jobs.length > 0 && (
        <div className="space-y-2">
          {jobs.map((job) => (
            <Card key={job.id}>
              <CardBody className="flex flex-wrap items-start justify-between gap-3 py-3.5">
                <div className="min-w-0 flex-1">
                  <Link
                    to={ROUTES.job(job.id)}
                    className="truncate text-sm font-medium hover:text-accent"
                    title={job.original_filename}
                  >
                    {truncate(job.original_filename, 70)}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                    <StatusBadge status={job.status} />
                    <span className="mono">{formatDateTime(job.created_at)}</span>
                    <span className="mono">{formatDuration(job.video_duration_seconds)}</span>
                    <span className="mono">{job.selected_model}</span>
                    {job.total_chunks ? <span className="mono">{job.total_chunks} chunks</span> : null}
                    {job.current_seo_score !== null && job.current_seo_score !== undefined ? (
                      <span className="mono">score {job.current_seo_score}</span>
                    ) : null}
                    {job.prompt_template_name_snapshot ? (
                      <span>{job.prompt_template_name_snapshot}</span>
                    ) : null}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Link to={ROUTES.job(job.id)}>
                    <Button variant="outline" size="sm">
                      Open
                    </Button>
                  </Link>
                  <JobActions job={job} compact />
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            disabled={filters.page <= 1}
            onClick={() => setFilters((previous) => ({ ...previous, page: previous.page - 1 }))}
          >
            Previous
          </Button>
          <span className="mono text-xs text-muted">
            Page {filters.page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={filters.page >= totalPages}
            onClick={() => setFilters((previous) => ({ ...previous, page: previous.page + 1 }))}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

export default HistoryPage;
