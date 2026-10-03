import { useMutation, useQuery } from '@tanstack/react-query';

import { QUERY_KEYS } from '../constants';
import {
  cancelJob,
  createJob,
  deleteJob,
  getJob,
  getJobChunks,
  getJobSourceInfo,
  getJobSummary,
  getTimeline,
  listJobEvents,
  listJobs,
  regenerateSeo,
  retryJob,
} from '../services/api/jobs';
import { queryClient } from './queryClient';

export function useJobsQuery(params) {
  return useQuery({
    queryKey: QUERY_KEYS.jobs(params),
    queryFn: () => listJobs(params),
    placeholderData: (previous) => previous,
  });
}

/**
 * Full job payload as the backend returns it:
 * { job, chunks, current_result_id, preflight }.
 */
export function useJobQuery(jobId, options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.job(jobId),
    queryFn: () => getJob(jobId),
    enabled: Boolean(jobId),
    ...options,
  });
}

/** Convenience view over `useJobQuery` for pages that only need the job row. */
export function useJobDetailQuery(jobId) {
  const query = useJobQuery(jobId);
  return {
    ...query,
    job: query.data?.job ?? null,
    chunks: query.data?.chunks ?? [],
    currentResultId: query.data?.current_result_id ?? null,
    preflight: query.data?.preflight ?? null,
  };
}

export function useJobSummaryQuery(jobId) {
  return useQuery({
    queryKey: QUERY_KEYS.jobSummary(jobId),
    queryFn: () => getJobSummary(jobId),
    enabled: Boolean(jobId),
  });
}

export function useJobChunksQuery(jobId) {
  return useQuery({
    queryKey: QUERY_KEYS.jobChunks(jobId),
    queryFn: () => getJobChunks(jobId),
    enabled: Boolean(jobId),
  });
}

export function useTimelineQuery(jobId) {
  return useQuery({
    queryKey: QUERY_KEYS.jobTimeline(jobId),
    queryFn: () => getTimeline(jobId),
    enabled: Boolean(jobId),
  });
}

export function useJobEventsQuery(jobId, params = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.jobEvents(jobId, params),
    queryFn: () => listJobEvents(jobId, params),
    enabled: Boolean(jobId),
  });
}

export function useJobSourceQuery(jobId) {
  return useQuery({
    queryKey: ['job', jobId, 'source'],
    queryFn: () => getJobSourceInfo(jobId),
    enabled: Boolean(jobId),
  });
}

function invalidateJob(jobId) {
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.job(jobId) });
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.jobSummary(jobId) });
  queryClient.invalidateQueries({ queryKey: QUERY_KEYS.jobEvents(jobId, {}) });
  queryClient.invalidateQueries({ queryKey: ['jobs'] });
}

export function useCreateJobMutation() {
  return useMutation({
    mutationFn: createJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  });
}

export function useCancelJobMutation(jobId) {
  return useMutation({
    mutationFn: () => cancelJob(jobId),
    onSuccess: () => invalidateJob(jobId),
  });
}

export function useRetryJobMutation(jobId) {
  return useMutation({
    mutationFn: () => retryJob(jobId),
    onSuccess: () => invalidateJob(jobId),
  });
}

export function useRegenerateSeoMutation(jobId) {
  return useMutation({
    mutationFn: (payload) => regenerateSeo(jobId, payload || {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.jobResults(jobId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.currentResult(jobId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.job(jobId) });
    },
  });
}

export function useDeleteJobMutation() {
  return useMutation({
    mutationFn: (jobId) => deleteJob(jobId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['jobs'] }),
  });
}
