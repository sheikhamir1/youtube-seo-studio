import { Clock, Download } from 'lucide-react';
import { useParams } from 'react-router-dom';

import TimelineOverview from '../components/timeline/TimelineOverview';
import TimelineView from '../components/timeline/TimelineView';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import PageHeader from '../components/ui/PageHeader';
import { SkeletonCard } from '../components/ui/Skeleton';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { useJobDetailQuery, useTimelineQuery } from '../queries/jobs';
import { formatDuration } from '../utils/format';

/**
 * Dedicated timeline page: the full content map with per-topic timestamps.
 * The JSON can be downloaded for external use.
 */
export function TimelinePage() {
  const { jobId } = useParams();
  const jobQuery = useJobDetailQuery(jobId);
  const timelineQuery = useTimelineQuery(jobId);
  const job = jobQuery.job;
  const timeline = timelineQuery.data;

  usePageTitle(job ? `Timeline · ${job.original_filename}` : 'Timeline');

  const downloadJson = () => {
    if (!timeline) return;
    const blob = new Blob([JSON.stringify(timeline, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `timeline-${jobId}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  if (jobQuery.isError) {
    return (
      <EmptyState
        title="Analysis not found"
        description="The timeline belongs to an analysis that no longer exists."
        action={
          <a href={ROUTES.history}>
            <Button variant="primary">Back to history</Button>
          </a>
        }
      />
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Content timeline"
        description={
          job
            ? `${job.original_filename} · ${formatDuration(job.video_duration_seconds)} · ${timeline?.topic_count || 0} topics`
            : 'AI-generated content map'
        }
        backTo={jobId ? ROUTES.job(jobId) : ROUTES.history}
        backLabel="Analysis"
        actions={
          <Button
            variant="outline"
            icon={Download}
            onClick={downloadJson}
            disabled={!timeline?.topics?.length}
          >
            Download JSON
          </Button>
        }
      />

      {timelineQuery.isLoading && <SkeletonCard rows={6} />}

      {timelineQuery.isError && (
        <Alert variant="error" title="Timeline unavailable">
          The timeline is produced after all chunks have been mapped. If the analysis is still
          running, check the processing page.
        </Alert>
      )}

      {timeline && (
        <>
          <Card>
            <CardHeader
              icon={Clock}
              title="Overview"
              description="Topics positioned proportionally along the video."
            />
            <CardBody>
              <TimelineOverview timeline={timeline} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Topics" description={timeline.note} />
            <CardBody>
              <TimelineView timeline={timeline} />
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

export default TimelinePage;
