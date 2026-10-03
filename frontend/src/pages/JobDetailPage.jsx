import { Download, LineChart, Loader2, Upload, Wand2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import ChunkTable from '../components/job/ChunkTable';
import JobActions from '../components/job/JobActions';
import SEOEditor from '../components/seo/SEOEditor';
import SeoOutputView from '../components/seo/SeoOutputView';
import VersionHistory from '../components/seo/VersionHistory';
import TimelineOverview from '../components/timeline/TimelineOverview';
import TimelineView from '../components/timeline/TimelineView';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import KeyValue from '../components/ui/KeyValue';
import PageHeader from '../components/ui/PageHeader';
import Select from '../components/ui/Select';
import { SkeletonCard } from '../components/ui/Skeleton';
import StatusBadge from '../components/ui/StatusBadge';
import Tabs from '../components/ui/Tabs';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { usePromptTemplates } from '../hooks/usePromptTemplates';
import { useJobDetailQuery, useRegenerateSeoMutation, useTimelineQuery } from '../queries/jobs';
import { useCurrentResultQuery, useResultsQuery } from '../queries/results';
import { useToastStore } from '../stores/toastStore';
import { extractChapters } from '../utils/chapters';
import { describeApiError } from '../utils/errors';
import {
  formatBytes,
  formatDateTime,
  formatDuration,
  formatNumber,
  truncate,
} from '../utils/format';

/**
 * Full record for one analysis: generated SEO (editable), every version, the
 * content timeline, per-chunk processing details and the frozen configuration.
 */
export function JobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const pushToast = useToastStore((state) => state.push);

  const [activeTab, setActiveTab] = useState('seo');
  const [isEditing, setIsEditing] = useState(false);
  const [regenerateTemplateId, setRegenerateTemplateId] = useState('');

  const jobQuery = useJobDetailQuery(jobId);
  const resultsQuery = useResultsQuery(jobId);
  const currentResultQuery = useCurrentResultQuery(jobId);
  const timelineQuery = useTimelineQuery(jobId);
  const regenerateMutation = useRegenerateSeoMutation(jobId);
  const { templates } = usePromptTemplates(regenerateTemplateId, setRegenerateTemplateId);

  const job = jobQuery.job;
  const results = resultsQuery.data?.items || [];
  const currentResultPayload = currentResultQuery.data;
  const currentResult =
    currentResultPayload?.result || results.find((result) => result.is_current) || null;
  const currentJobStatus = currentResultPayload?.job_status || jobQuery.job?.status || null;
  const noResultMessage = currentResultPayload?.message;

  usePageTitle(job ? truncate(job.original_filename, 34) : 'Analysis');

  const currentResultId = currentResult?.id;
  useEffect(() => {
    // A different result version always opens in read-only mode.
    setIsEditing(false);
  }, [currentResultId]);

  const chapters = useMemo(
    () => (currentResult ? extractChapters(currentResult.description) : []),
    [currentResult],
  );

  if (jobQuery.isError) {
    return (
      <EmptyState
        title="Analysis not found"
        description="It may have been deleted from local storage."
        action={
          <Link to={ROUTES.history}>
            <Button variant="primary">Back to history</Button>
          </Link>
        }
      />
    );
  }

  if (jobQuery.isLoading || !job) {
    return (
      <div className="space-y-4">
        <SkeletonCard rows={4} />
        <SkeletonCard rows={6} />
      </div>
    );
  }

  const regenerate = async () => {
    try {
      await regenerateMutation.mutateAsync({
        prompt_template_id: regenerateTemplateId || job.prompt_template_id,
        selected_model: job.selected_model,
      });
      pushToast({
        variant: 'success',
        title: 'Regeneration started',
        description: 'A new version will appear here when the Reduce phase finishes.',
      });
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  const tabs = [
    { value: 'seo', label: 'SEO output' },
    { value: 'versions', label: 'Versions', count: results.length },
    { value: 'timeline', label: 'Timeline', count: timelineQuery.data?.topic_count },
    { value: 'chunks', label: 'Processing', count: jobQuery.chunks.length },
    { value: 'config', label: 'Configuration' },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title={job.original_filename}
        description={`${formatDuration(job.video_duration_seconds)} · ${formatBytes(job.source_size_bytes)} · ${job.selected_model}`}
        backTo={ROUTES.history}
        backLabel="History"
        meta={
          <>
            <StatusBadge status={job.status} />
            <span className="mono">created {formatDateTime(job.created_at)}</span>
            {job.completed_at && <span className="mono">completed {formatDateTime(job.completed_at)}</span>}
            {currentResult && <span className="mono">score {currentResult.seo_score}/100</span>}
            {job.prompt_template_name_snapshot && <span>{job.prompt_template_name_snapshot}</span>}
          </>
        }
        actions={
          <JobActions
            job={job}
            compact
            onDeleted={() => navigate(ROUTES.history)}
            onRegenerate={regenerate}
          />
        }
      />

      {job.status === 'FAILED' && (
        <Alert variant="error" title={`Failed during ${job.failed_stage || 'processing'}`}>
          <p>{job.current_error_message}</p>
          {job.current_error_code && (
            <p className="mono mt-1 text-xs text-muted">code: {job.current_error_code}</p>
          )}
        </Alert>
      )}

      {['QUEUED', 'VALIDATING', 'EXTRACTING', 'CHUNKING', 'MAPPING', 'REDUCING'].includes(job.status) && (
        <Alert variant="info" title="This analysis is still running">
          <p>
            Live progress is on the processing page. The SEO output below appears once the Reduce
            phase has produced a validated version.
          </p>
          <div className="mt-2">
            <Link to={ROUTES.processing(jobId)}>
              <Button variant="outline" size="sm">
                Open live view
              </Button>
            </Link>
          </div>
        </Alert>
      )}

      {timelineQuery.data?.topics?.length > 0 && (
        <Card>
          <CardHeader
            icon={LineChart}
            title="Content map"
            description="Every AI-detected topic drawn on the video timeline."
            actions={
              <Link to={ROUTES.timeline(jobId)}>
                <Button variant="ghost" size="xs" icon={Download}>
                  Full timeline
                </Button>
              </Link>
            }
          />
          <CardBody>
            <TimelineOverview timeline={timelineQuery.data} />
          </CardBody>
        </Card>
      )}

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'seo' && (
        <div className="space-y-4">
          {!currentResult && (
            <EmptyState
              title="No SEO output yet"
              description={
                noResultMessage ||
                (currentJobStatus === 'COMPLETED'
                  ? 'This analysis finished without a saved result. Regenerate to produce one.'
                  : 'The generated metadata appears here when the Reduce phase completes.')
              }
              action={
                currentJobStatus === 'COMPLETED' ? (
                  <Button variant="primary" icon={Wand2} onClick={regenerate} isLoading={regenerateMutation.isPending}>
                    Regenerate SEO
                  </Button>
                ) : null
              }
            />
          )}

          {currentResult &&
            (isEditing ? (
              <SEOEditor
                key={currentResult.id}
                jobId={jobId}
                result={currentResult}
                videoDurationSeconds={job.video_duration_seconds}
                onSaved={() => setIsEditing(false)}
              />
            ) : (
              <SeoOutputView
                result={currentResult}
                job={job}
                chapters={currentResult.chapters?.length ? currentResult.chapters : chapters}
                onEdit={() => setIsEditing(true)}
              />
            ))}

          {currentResult && (
            <Card>
              <CardHeader
                icon={Wand2}
                title="Regenerate"
                description="Runs the Reduce phase again over the stored timeline. Existing versions are kept."
              />
              <CardBody className="flex flex-wrap items-end gap-3">
                <div className="min-w-[240px] flex-1">
                  <Select
                    label="Prompt template"
                    options={templates.map((template) => ({
                      value: template.id,
                      label: template.name,
                    }))}
                    value={regenerateTemplateId || job.prompt_template_id || ''}
                    onChange={(event) => setRegenerateTemplateId(event.target.value)}
                  />
                </div>
                <Button
                  variant="primary"
                  icon={Wand2}
                  isLoading={regenerateMutation.isPending}
                  onClick={regenerate}
                >
                  Regenerate SEO
                </Button>
              </CardBody>
            </Card>
          )}

          {currentResult && (
            <Card>
              <CardHeader
                icon={Upload}
                title="Publish to YouTube"
                description="Send this SEO metadata to a YouTube video."
              />
              <CardBody>
                <Link to={`${ROUTES.publishYouTube(jobId)}?title=${encodeURIComponent(currentResult.title)}&description=${encodeURIComponent(currentResult.description)}&tags=${encodeURIComponent((currentResult.tags || []).join(','))}`}>
                  <Button variant="primary" icon={Upload}>
                    Open YouTube Publisher
                  </Button>
                </Link>
              </CardBody>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'versions' && (
        <Card>
          <CardHeader
            title="Result versions"
            description="Each Reduce run creates an immutable version."
          />
          <CardBody>
            {resultsQuery.isLoading ? (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Loading versions…
              </p>
            ) : (
              <VersionHistory jobId={jobId} results={results} currentId={currentResult?.id} />
            )}
          </CardBody>
        </Card>
      )}

      {activeTab === 'timeline' && (
        <Card>
          <CardHeader
            title="Content timeline"
            description="Normalized Map output, rebased onto the video's own timeline."
            actions={
              <Link to={ROUTES.timeline(jobId)}>
                <Button variant="outline" size="sm">
                  Open full page
                </Button>
              </Link>
            }
          />
          <CardBody>
            {timelineQuery.isLoading ? (
              <p className="text-sm text-muted">Loading timeline…</p>
            ) : (
              <TimelineView timeline={timelineQuery.data} />
            )}
          </CardBody>
        </Card>
      )}

      {activeTab === 'chunks' && (
        <Card>
          <CardHeader
            title="Chunk processing"
            description="Token usage and attempts per chunk - the durable unit of the pipeline."
          />
          <CardBody>
            <ChunkTable chunks={jobQuery.chunks} />
          </CardBody>
        </Card>
      )}

      {activeTab === 'config' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Job record" description="Frozen snapshot of this analysis." />
            <CardBody>
              <KeyValue
                items={[
                  { label: 'Job ID', value: <span className="mono">{job.id}</span> },
                  { label: 'Status', value: job.status },
                  { label: 'Stage', value: job.stage },
                  { label: 'Progress', value: `${job.progress_percent}%`, mono: true },
                  { label: 'Attempts', value: job.attempt_count, mono: true },
                  { label: 'Chunks', value: job.total_chunks ?? '—', mono: true },
                  {
                    label: 'Source size',
                    value: formatBytes(job.source_size_bytes),
                    mono: true,
                  },
                  {
                    label: 'Video duration',
                    value: formatDuration(job.video_duration_seconds),
                    mono: true,
                  },
                  {
                    label: 'Audio duration',
                    value: formatDuration(job.audio_duration_seconds),
                    mono: true,
                  },
                  {
                    label: 'Audio stream',
                    value:
                      job.audio_stream_index !== null
                        ? `#${job.audio_stream_index}${job.audio_stream_language ? ` (${job.audio_stream_language})` : ''}`
                        : '—',
                    mono: true,
                  },
                  {
                    label: 'Audio offset',
                    value: `${job.audio_stream_start_offset_seconds}s`,
                    mono: true,
                  },
                ]}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="SEO context used" description="Exactly what was sent as context." />
            <CardBody>
              <KeyValue
                items={[
                  { label: 'Working title', value: job.seo_context?.video_title || '—' },
                  { label: 'Primary keyword', value: job.seo_context?.primary_keyword || '—' },
                  {
                    label: 'Secondary keywords',
                    value: job.seo_context?.secondary_keywords?.length
                      ? job.seo_context.secondary_keywords.join(', ')
                      : '—',
                  },
                  { label: 'Target audience', value: job.seo_context?.target_audience || '—' },
                  { label: 'Content language', value: job.seo_context?.content_language || 'auto' },
                  { label: 'SEO language', value: job.seo_context?.seo_language || 'auto' },
                  { label: 'Content type', value: job.seo_context?.content_type || 'auto' },
                  { label: 'Tone', value: job.seo_context?.tone || 'auto' },
                ]}
              />
            </CardBody>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader
              title="Pipeline configuration"
              description="Stored with the job, so old analyses remain reproducible."
            />
            <CardBody>
              <KeyValue
                columns={3}
                items={Object.entries(job.pipeline_config || {}).map(([key, value]) => ({
                  label: key.replace(/_/g, ' '),
                  value: typeof value === 'object' ? JSON.stringify(value) : String(value),
                  mono: true,
                }))}
              />
              {jobQuery.preflight && (
                <div className="mt-4 rounded-md border border-border bg-surface-2 p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">
                    Request estimate (pre-flight)
                  </p>
                  <p className="mt-1 text-sm text-muted">
                    {formatNumber(jobQuery.preflight.chunk_count)} chunk request(s) plus{' '}
                    {jobQuery.preflight.reduce_requests ?? 1} Reduce request ·≈{' '}
                    {formatNumber(jobQuery.preflight.total_estimated_tokens)} tokens
                    {jobQuery.preflight.warning ? ` · ${jobQuery.preflight.warning}` : ''}
                  </p>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}

export default JobDetailPage;
