import { ArrowRight, Ban, RotateCcw, Terminal } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import ChunkTable from '../components/job/ChunkTable';
import EventLog from '../components/job/EventLog';
import JobActions from '../components/job/JobActions';
import PipelineStageList from '../components/job/PipelineStageList';
import ProgressPanel from '../components/job/ProgressPanel';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import PageHeader from '../components/ui/PageHeader';
import StatusBadge from '../components/ui/StatusBadge';
import { ROUTES, isTerminalStatus } from '../constants';
import { useJobStream } from '../hooks/useJobStream';
import { usePageTitle } from '../hooks/usePageTitle';
import {
  useJobChunksQuery,
  useJobDetailQuery,
  useJobEventsQuery,
  useRetryJobMutation,
} from '../queries/jobs';
import { useToastStore } from '../stores/toastStore';
import { describeApiError } from '../utils/errors';
import { truncate } from '../utils/format';

const PAGE_SIZE = 200;

/**
 * Live processing view.
 *
 * All progress arrives over SSE (`/jobs/:id/events/stream`) and is merged with
 * the persisted job snapshot. No polling, and no client-side simulation of
 * progress: the percentage shown is the backend's own weighted progress.
 */
export function ProcessingPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const pushToast = useToastStore((state) => state.push);
  const [eventsPage, setEventsPage] = useState(1);

  const jobQuery = useJobDetailQuery(jobId);
  const chunksQuery = useJobChunksQuery(jobId);
  const eventsQuery = useJobEventsQuery(jobId, { page: eventsPage, pageSize: PAGE_SIZE });
  const retryMutation = useRetryJobMutation(jobId);

  const [job, setJob] = useState(null);
  useEffect(() => {
    if (jobQuery.job) setJob((previous) => ({ ...(previous || {}), ...jobQuery.job }));
  }, [jobQuery.job]);

  const handleTerminal = useCallback(
    (progress) => {
      // Refresh the authoritative snapshot once the stream signals completion.
      jobQuery.refetch();
      chunksQuery.refetch();
      eventsQuery.refetch();
      if (progress?.status === 'COMPLETED') {
        pushToast({
          variant: 'success',
          title: 'Analysis complete',
          description: 'SEO metadata is ready to review and copy.',
        });
      }
      if (progress?.status === 'FAILED') {
        pushToast({
          variant: 'error',
          title: 'Analysis failed',
          description: progress.error_message || 'Open the log below for the failing stage.',
        });
      }
    },
    [jobQuery, chunksQuery, eventsQuery, pushToast],
  );

  const { connected, snapshot, events, lastProgress } = useJobStream(jobId, {
    enabled: Boolean(jobId),
    onStatusChange: () => {},
    onTerminal: handleTerminal,
  });

  // Live status/stage/error from the stream, without inventing values.
  useEffect(() => {
    if (!snapshot) return;
    setJob((previous) => ({ ...(previous || {}), ...snapshot }));
  }, [snapshot]);

  useEffect(() => {
    if (!lastProgress) return;
    setJob((previous) =>
      previous
        ? {
            ...previous,
            status: lastProgress.status,
            stage: lastProgress.stage,
            progress_percent: lastProgress.progress_percent,
            current_chunk_index: lastProgress.current_chunk ?? previous.current_chunk_index,
            total_chunks: lastProgress.total_chunks ?? previous.total_chunks,
            current_error_code: lastProgress.error_code,
            current_error_message: lastProgress.error_message,
            failed_stage: lastProgress.failed_stage,
            failed_chunk_index: lastProgress.failed_chunk_index,
          }
        : previous,
    );
  }, [lastProgress]);

  const terminal = job ? isTerminalStatus(job.status) : false;
  usePageTitle(job ? `Processing ${truncate(job.original_filename, 30)}` : 'Processing');

  if (jobQuery.isError) {
    return (
      <EmptyState
        title="Analysis not found"
        description="This analysis may have been deleted. Check the history page."
        action={
          <Link to={ROUTES.history}>
            <Button variant="primary">Go to history</Button>
          </Link>
        }
      />
    );
  }

  const historicalEvents = eventsQuery.data?.items || [];
  const hasMoreEvents = (eventsQuery.data?.total || 0) > eventsPage * PAGE_SIZE;

  const retry = async () => {
    try {
      await retryMutation.mutateAsync();
      pushToast({ variant: 'success', title: 'Re-queued', description: 'Processing resumes from the first unfinished chunk.' });
      eventsQuery.refetch();
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title={job?.original_filename || 'Processing'}
        description="Progress is reported by the worker. Completed chunks are durable, so a crash or restart resumes instead of starting over."
        backTo={ROUTES.history}
        backLabel="History"
        actions={
          <>
            {job && <StatusBadge status={job.status} />}
            {job && <JobActions job={job} compact onDeleted={() => navigate(ROUTES.history)} />}
          </>
        }
      />

      {job?.status === 'FAILED' && (
        <Alert
          variant="error"
          title={`Failed during ${job.failed_stage || 'processing'}`}
          actions={
            <Button variant="outline" size="sm" icon={RotateCcw} onClick={retry} isLoading={retryMutation.isPending}>
              Retry from last completed step
            </Button>
          }
        >
          <p>{job.current_error_message}</p>
          {job.current_error_code && (
            <p className="mono mt-1 text-xs text-muted">code: {job.current_error_code}</p>
          )}
          <p className="mt-1 text-xs text-muted">
            {job.attempt_count} attempt{job.attempt_count === 1 ? '' : 's'} so far. Retrying never
            re-processes chunks that already succeeded.
          </p>
        </Alert>
      )}

      {job?.status === 'CANCELED' && (
        <Alert variant="warning" title="Canceled">
          <p>
            Processing stopped{job.failed_chunk_index !== null && job.failed_chunk_index !== undefined
              ? ` at chunk ${job.failed_chunk_index + 1}`
              : ''}
            . {job.total_chunks ? `${job.total_chunks} chunks were planned.` : ''}
          </p>
          <div className="mt-2">
            <Button variant="outline" size="sm" icon={RotateCcw} onClick={retry} isLoading={retryMutation.isPending}>
              Resume this analysis
            </Button>
          </div>
        </Alert>
      )}

      {job?.cancel_requested && job.status !== 'CANCELED' && (
        <Alert variant="info" title="Cancellation requested">
          <p className="flex items-center gap-1.5">
            <Ban className="h-3.5 w-3.5" aria-hidden="true" />
            The worker finishes the current safe step, then stops.
          </p>
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader
            title="Pipeline progress"
            description={job ? `Stage ${job.stage} · model ${job.selected_model}` : undefined}
            actions={
              connected ? (
                <span className="text-xs text-success">streaming</span>
              ) : (
                <span className="text-xs text-muted">connecting…</span>
              )
            }
          />
          <CardBody>
            {jobQuery.isLoading && !job ? (
              <p className="text-sm text-muted">Loading analysis…</p>
            ) : (
              <ProgressPanel job={job} lastProgress={lastProgress} connected={connected} />
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Stages" description="Exactly what each step does." />
          <CardBody>
            <PipelineStageList job={job} />
          </CardBody>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader
            icon={Terminal}
            title="Processing log"
            description="Newest entries at the bottom; live events stream in as they happen."
          />
          <CardBody>
            <EventLog
              events={[...events].reverse()}
              historical={historicalEvents}
              hasMore={hasMoreEvents}
              isLoadingMore={eventsQuery.isFetching && eventsPage > 1}
              onLoadMore={() => setEventsPage((page) => page + 1)}
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Chunks" description="The durable unit of the Map phase." />
          <CardBody>
            <ChunkTable chunks={chunksQuery.data?.items || []} isLoading={chunksQuery.isLoading} />
          </CardBody>
        </Card>
      </div>

      {terminal && (
        <Card>
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">
                {job.status === 'COMPLETED' ? 'Metadata is ready' : 'Processing finished'}
              </p>
              <p className="text-xs text-muted">
                {job.status === 'COMPLETED'
                  ? 'Review, edit and copy the generated SEO from the analysis page.'
                  : 'Open the analysis page for the full record, or retry to resume.'}
              </p>
            </div>
            <Link to={ROUTES.job(jobId)}>
              <Button variant="primary" icon={ArrowRight}>
                Open analysis
              </Button>
            </Link>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

export default ProcessingPage;
