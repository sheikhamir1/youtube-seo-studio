import { useMemo, useState } from 'react';

import { formatTimestamp } from '../../utils/format';
import { cn } from '../../utils/cn';
import Input from '../ui/Input';
import EmptyState from '../ui/EmptyState';

/**
 * Timeline visualization: topics positioned on the real video duration, with
 * search. Timestamps come from the normalized Map output, so they are
 * AI-derived content timestamps, not frame-accurate cuts.
 */
export function TimelineView({ timeline, currentTimeSeconds = null }) {
  const [search, setSearch] = useState('');
  const topics = useMemo(() => timeline?.topics || [], [timeline]);
  const duration = timeline?.video_duration_seconds || (topics.length ? Math.max(...topics.map((topic) => topic.end_seconds)) : 0);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return topics;
    return topics.filter(
      (topic) =>
        topic.topic.toLowerCase().includes(needle) || topic.summary.toLowerCase().includes(needle),
    );
  }, [topics, search]);

  if (!topics.length) {
    return (
      <EmptyState
        title="No timeline yet"
        description="The timeline is built from the Map phase output once all chunks have been processed."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          {topics.length} topics over {formatTimestamp(duration)}
        </p>
        <div className="w-56">
          <Input
            placeholder="Search topics…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label="Search timeline topics"
          />
        </div>
      </div>

      <ol className="space-y-2">
        {filtered.map((topic, index) => {
          const startPercent = duration ? (topic.start_seconds / duration) * 100 : 0;
          const widthPercent = duration
            ? Math.max(1, ((topic.end_seconds - topic.start_seconds) / duration) * 100)
            : 0;
          const isCurrent =
            currentTimeSeconds !== null &&
            currentTimeSeconds >= topic.start_seconds &&
            currentTimeSeconds < topic.end_seconds;

          return (
            <li
              key={`${topic.topic}-${topic.start_seconds}-${index}`}
              className={cn(
                'rounded-md border p-3',
                isCurrent ? 'border-accent bg-accent/5' : 'border-border',
              )}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{topic.topic}</p>
                  <p className="mt-0.5 text-sm text-muted">{topic.summary}</p>
                </div>
                <span className="mono shrink-0 text-xs text-muted">
                  {formatTimestamp(topic.start_seconds)} – {formatTimestamp(topic.end_seconds)}
                </span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-accent/70"
                  style={{ marginLeft: `${startPercent}%`, width: `${widthPercent}%` }}
                />
              </div>
              {topic.source_chunk_indices?.length > 0 && (
                <p className="mono mt-1 text-[11px] text-muted">
                  from chunk{topic.source_chunk_indices.length > 1 ? 's' : ''}{' '}
                  {topic.source_chunk_indices.map((value) => value + 1).join(', ')}
                </p>
              )}
            </li>
          );
        })}
      </ol>

      {!filtered.length && (
        <EmptyState compact title="No topics match that search" description={`Nothing matched “${search}”.`} />
      )}

      <p className="text-xs text-muted">
        Timestamps are derived from the AI content map (segment start + audio offset). They are
        accurate to a few seconds, not frame-accurate.
      </p>
    </div>
  );
}

export default TimelineView;
