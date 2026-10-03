import { SlidersHorizontal } from 'lucide-react';

import { PIPELINE_STAGE_ORDER } from '../job/PipelineStageList';
import { Card, CardBody, CardHeader } from '../ui/Card';
import KeyValue from '../ui/KeyValue';
import { LoadingBlock } from '../ui/Spinner';
import Alert from '../ui/Alert';

/**
 * Read-only view of the effective pipeline configuration the backend reports in
 * each job snapshot. Values come from the job record, not from guesswork.
 */
export function ProcessingDefaults({ job, isLoading }) {
  if (isLoading) return <LoadingBlock label="Loading pipeline configuration…" />;
  if (!job) {
    return (
      <Card>
        <CardHeader
          icon={SlidersHorizontal}
          title="Pipeline configuration"
          description="Chunking and output rules applied to every analysis."
        />
        <CardBody>
          <Alert variant="info" title="No job selected">
            Open any analysis and this panel shows the exact pipeline configuration it ran with.
          </Alert>
        </CardBody>
      </Card>
    );
  }

  const config = job.pipeline_config || {};

  return (
    <Card>
      <CardHeader
        icon={SlidersHorizontal}
        title="Pipeline configuration"
        description={`Applied to job ${job.id.slice(0, 8)} (snapshot stored with the job).`}
      />
      <CardBody className="space-y-4">
        <KeyValue
          columns={2}
          items={[
            { label: 'Chunk duration', value: `${config.chunk_duration_seconds ?? '—'} s`, mono: true },
            { label: 'Chunk overlap', value: `${config.chunk_overlap_seconds ?? '—'} s`, mono: true },
            { label: 'Chunk step', value: `${config.chunk_step_seconds ?? '—'} s`, mono: true },
            { label: 'Audio seconds / token', value: config.audio_tokens_per_second ?? '—', mono: true },
            { label: 'Map requests in flight', value: config.map_concurrency ?? 1, mono: true },
            { label: 'Min interval', value: `${config.min_interval_seconds ?? '—'} s`, mono: true },
            { label: 'Max retries', value: config.max_retries ?? '—', mono: true },
            { label: 'Schema repairs', value: config.max_schema_repairs ?? '—', mono: true },
            { label: 'Title limit', value: `${config.title_max_chars ?? '—'} chars`, mono: true },
            { label: 'Description limit', value: `${config.description_max_chars ?? '—'} chars`, mono: true },
          ]}
        />

        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
            Progress weights
          </p>
          <ul className="flex flex-wrap gap-2">
            {PIPELINE_STAGE_ORDER.map((stage) => (
              <li
                key={stage.key}
                className="mono rounded border border-border bg-surface-2 px-2 py-0.5 text-xs"
              >
                {stage.label}: {config.stage_weights?.[stage.key] ?? '—'}%
              </li>
            ))}
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}

export default ProcessingDefaults;
