import { useEffect, useMemo, useRef, useState } from 'react';

import { EVENT_LEVEL_STYLES } from '../../constants';
import { formatTime } from '../../utils/format';
import { cn } from '../../utils/cn';
import Button from '../ui/Button';
import EmptyState from '../ui/EmptyState';

/**
 * Live processing log. Events arrive over SSE; the user can pause the
 * auto-scroll to read something without losing incoming lines.
 */
export function EventLog({ events = [], historical = [], onLoadMore, hasMore = false, isLoadingMore = false }) {
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef(null);

  const lines = useMemo(() => {
    const seen = new Set();
    const merged = [...historical, ...events].filter((event) => {
      const key = `${event.created_at}-${event.message}-${event.chunk_index ?? ''}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    return merged;
  }, [events, historical]);

  useEffect(() => {
    if (!autoScroll || !containerRef.current) return;
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [lines.length, autoScroll]);

  if (!lines.length) {
    return (
      <EmptyState
        compact
        title="No log entries yet"
        description="Processing events appear here as the worker moves through the pipeline."
      />
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs text-muted">{lines.length} entries</p>
        <div className="flex items-center gap-2">
          {hasMore && (
            <Button variant="ghost" size="xs" onClick={onLoadMore} isLoading={isLoadingMore}>
              Load earlier
            </Button>
          )}
          <Button
            variant={autoScroll ? 'outline' : 'ghost'}
            size="xs"
            onClick={() => setAutoScroll((value) => !value)}
          >
            {autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
          </Button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="max-h-[380px] overflow-y-auto rounded-md border border-border bg-surface-2 scrollbar-thin"
        onScroll={(event) => {
          const element = event.currentTarget;
          const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 24;
          if (!atBottom && autoScroll) setAutoScroll(false);
        }}
      >
        <ul className="divide-y divide-border/60">
          {lines.map((event, index) => (
            <li
              key={`${event.created_at}-${index}`}
              className="flex gap-3 px-3 py-1.5 text-xs leading-relaxed"
            >
              <span className="mono shrink-0 text-muted">{formatTime(event.created_at)}</span>
              {event.progress_percent !== null && event.progress_percent !== undefined && (
                <span className="mono w-12 shrink-0 text-right tabular-nums text-muted">
                  {Number(event.progress_percent).toFixed(0)}%
                </span>
              )}
              <span className={cn('min-w-0 flex-1', EVENT_LEVEL_STYLES[event.level] || 'text-muted')}>
                {event.message}
                {event.chunk_index !== null && event.chunk_index !== undefined && (
                  <span className="mono ml-1.5 text-muted">[chunk {event.chunk_index + 1}]</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default EventLog;
