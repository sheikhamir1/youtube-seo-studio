import { Badge } from '../ui/Badge';
import EmptyState from '../ui/EmptyState';
import { formatDuration, formatNumber, formatTimestamp } from '../../utils/format';

const STATUS_VARIANT = {
  PENDING: 'neutral',
  PROCESSING: 'accent',
  COMPLETED: 'success',
  FAILED: 'danger',
};

/** Per-chunk processing table: the durable unit of the Map phase. */
export function ChunkTable({ chunks = [], isLoading = false }) {
  if (isLoading) {
    return <p className="text-sm text-muted">Loading chunks…</p>;
  }
  if (!chunks.length) {
    return (
      <EmptyState
        compact
        title="No chunks yet"
        description="Chunks appear after the audio extraction and chunking stages finish."
      />
    );
  }

  const completed = chunks.filter((chunk) => chunk.status === 'COMPLETED').length;
  const failed = chunks.filter((chunk) => chunk.status === 'FAILED').length;

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>
          {completed} of {chunks.length} chunks completed
        </span>
        {failed > 0 && <Badge variant="danger">{failed} failed</Badge>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="py-2 pr-3 font-medium">#</th>
              <th className="py-2 pr-3 font-medium">Range</th>
              <th className="py-2 pr-3 font-medium">Duration</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 pr-3 font-medium">Attempts</th>
              <th className="py-2 pr-3 font-medium">Tokens in/out</th>
              <th className="py-2 pr-3 font-medium">Topics</th>
            </tr>
          </thead>
          <tbody>
            {chunks.map((chunk) => (
              <tr key={chunk.id} className="border-b border-border/60 last:border-0">
                <td className="mono py-2 pr-3 text-muted">{chunk.chunk_index + 1}</td>
                <td className="mono py-2 pr-3">
                  {formatTimestamp(chunk.start_seconds)} – {formatTimestamp(chunk.end_seconds)}
                </td>
                <td className="mono py-2 pr-3 text-muted">{formatDuration(chunk.duration_seconds)}</td>
                <td className="py-2 pr-3">
                  <Badge variant={STATUS_VARIANT[chunk.status] || 'neutral'}>{chunk.status}</Badge>
                  {chunk.error_message && (
                    <p className="mt-1 max-w-[260px] text-xs text-danger">{chunk.error_message}</p>
                  )}
                </td>
                <td className="mono py-2 pr-3 text-muted">{chunk.attempt_count}</td>
                <td className="mono py-2 pr-3 text-muted">
                  {formatNumber(chunk.actual_input_tokens ?? chunk.estimated_input_tokens)} /{' '}
                  {formatNumber(chunk.actual_output_tokens)}
                </td>
                <td className="mono py-2 pr-3 text-muted">{chunk.topic_count ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ChunkTable;
