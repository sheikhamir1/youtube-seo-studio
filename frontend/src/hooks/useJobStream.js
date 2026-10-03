import { useEffect, useRef, useState } from 'react';

import { apiUrl } from '../services/api/client';
import { isTerminalStatus } from '../constants';

/**
 * Server-Sent Events stream for one job.
 *
 * The job detail page reconnects automatically when the stream drops, uses the
 * `snapshot` event as the initial state and appends log events as they arrive.
 * No polling is used anywhere for progress.
 */
const MAX_EVENTS = 500;

/** Job event types emitted by the backend (see app/core/enums.py). */
export const JOB_EVENT_TYPES = [
  'job_created',
  'job_started',
  'validation_started',
  'validation_completed',
  'extraction_started',
  'extraction_progress',
  'extraction_completed',
  'chunking_started',
  'chunk_created',
  'chunking_completed',
  'mapping_started',
  'chunk_mapping_started',
  'chunk_mapping_completed',
  'gemini_retry',
  'gemini_file_cleanup_failed',
  'timeline_normalized',
  'reduce_started',
  'reduce_completed',
  'seo_validated',
  'seo_version_created',
  'cancel_requested',
  'job_canceled',
  'job_failed',
  'job_completed',
  'job_retry_queued',
  'job_recovered',
  'worker_heartbeat_stale',
];

export function useJobStream(jobId, { enabled = true, onStatusChange, onTerminal } = {}) {
  const [connected, setConnected] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [events, setEvents] = useState([]);
  const [lastProgress, setLastProgress] = useState(null);
  const [error, setError] = useState(null);
  const sourceRef = useRef(null);
  const retryRef = useRef(null);
  const closedRef = useRef(false);
  const terminalRef = useRef(false);
  const statusChangeRef = useRef(onStatusChange);
  const terminalRefCb = useRef(onTerminal);

  statusChangeRef.current = onStatusChange;
  terminalRefCb.current = onTerminal;

  useEffect(() => {
    if (!jobId || !enabled) return undefined;
    closedRef.current = false;
    terminalRef.current = false;
    let attempt = 0;

    const connect = () => {
      if (closedRef.current) return;
      const url = apiUrl(`/jobs/${jobId}/events/stream`);
      const source = new EventSource(url);
      sourceRef.current = source;

      source.onopen = () => {
        attempt = 0;
        setConnected(true);
        setError(null);
      };

      source.addEventListener('snapshot', (message) => {
        try {
          const payload = JSON.parse(message.data);
          setSnapshot(payload.job || payload);
          if (payload.job?.status) statusChangeRef.current?.(payload.job.status);
        } catch (parseError) {
          setError(parseError);
        }
      });

      source.addEventListener('progress', (message) => {
        try {
          const payload = JSON.parse(message.data);
          setLastProgress(payload);
          statusChangeRef.current?.(payload.status);
          if (isTerminalStatus(payload.status)) {
            terminalRef.current = true;
            terminalRefCb.current?.(payload);
            source.close();
            setConnected(false);
          }
        } catch (parseError) {
          setError(parseError);
        }
      });

      source.addEventListener('done', (message) => {
        terminalRef.current = true;
        try {
          terminalRefCb.current?.(JSON.parse(message.data));
        } catch {
          terminalRefCb.current?.({});
        }
        source.close();
        setConnected(false);
      });

      // The backend names every SSE frame after its job-event type, lowercased.
      JOB_EVENT_TYPES.forEach((eventName) => {
        source.addEventListener(eventName, (message) => {
          try {
            const payload = JSON.parse(message.data);
            setEvents((previous) => [...previous.slice(-MAX_EVENTS + 1), payload]);
          } catch {
            /* ignore malformed frames */
          }
        });
      });

      source.onerror = () => {
        setConnected(false);
        source.close();
        if (closedRef.current || terminalRef.current) return;
        attempt += 1;
        const delay = Math.min(8000, 1000 * 2 ** Math.min(attempt, 3));
        retryRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closedRef.current = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      sourceRef.current?.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [jobId, enabled]);

  return { connected, snapshot, events, lastProgress, error, clearEvents: () => setEvents([]) };
}
