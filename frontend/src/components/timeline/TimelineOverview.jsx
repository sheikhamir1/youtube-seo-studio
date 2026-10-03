import { useMemo } from 'react';

import { formatShortDuration, formatTimestamp } from '../../utils/format';
import EmptyState from '../ui/EmptyState';

/**
 * Proportional overview strip: every topic drawn on a single video-length bar.
 * Hovering a segment reveals its title and range.
 */
export function TimelineOverview({ timeline }) {
  const topics = useMemo(() => timeline?.topics || [], [timeline]);
  const duration = useMemo(() => {
    if (timeline?.video_duration_seconds) return timeline.video_duration_seconds;
    if (!topics.length) return 0;
    return Math.max(...topics.map((topic) => topic.end_seconds));
  }, [timeline, topics]);

  if (!topics.length || !duration) {
    return <EmptyState compact title="No timeline data" description="Process a video to see its content map." />;
  }

  const markers = [0, 0.25, 0.5, 0.75, 1].map((ratio) => Math.round(duration * ratio));

  return (
    <div>
      <div className="relative h-11 w-full overflow-hidden rounded-md border border-border bg-surface-2">
        {topics.map((topic, index) => {
          const left = (topic.start_seconds / duration) * 100;
          const width = Math.max(0.6, ((topic.end_seconds - topic.start_seconds) / duration) * 100);
          return (
            <div
              key={`${topic.topic}-${index}`}
              title={`${formatTimestamp(topic.start_seconds)} – ${formatTimestamp(topic.end_seconds)} · ${topic.topic}`}
              className="absolute top-0 h-full border-r border-bg/70 transition-colors hover:bg-accent/40"
              style={{
                left: `${left}%`,
                width: `${Math.min(width, 100 - left)}%`,
                backgroundColor: `hsl(${(index * 47) % 360} 70% 55% / 0.35)`,
              }}
            >
              <span className="pointer-events-none absolute left-1 top-1 max-w-full truncate pr-2 text-[10px] font-medium text-content/80">
                {width > 6 ? topic.topic : ''}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mono mt-1 flex justify-between text-[11px] text-muted">
        {markers.map((marker) => (
          <span key={marker}>{formatShortDuration(marker)}</span>
        ))}
      </div>
    </div>
  );
}

export default TimelineOverview;
