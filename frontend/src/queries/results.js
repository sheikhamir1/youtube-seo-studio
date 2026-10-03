import { useMutation, useQuery } from '@tanstack/react-query';

import { QUERY_KEYS } from '../constants';
import {
  getCurrentResult,
  listResults,
  restoreResult,
  updateResult,
  validateDescription,
} from '../services/api/results';
import { queryClient } from './queryClient';

export function useResultsQuery(jobId) {
  return useQuery({
    queryKey: QUERY_KEYS.jobResults(jobId),
    queryFn: () => listResults(jobId),
    enabled: Boolean(jobId),
  });
}

/**
 * `GET /jobs/:id/results/current` answers with
 * `{ result, job_status, message? }` where `result` is null until the Reduce
 * phase has produced a validated version. The payload is kept intact so the UI
 * can explain *why* there is no result yet instead of showing a blank panel.
 */
export function useCurrentResultQuery(jobId) {
  return useQuery({
    queryKey: QUERY_KEYS.currentResult(jobId),
    queryFn: () => getCurrentResult(jobId),
    enabled: Boolean(jobId),
  });
}

export function useSaveResultMutation(jobId) {
  return useMutation({
    mutationFn: ({ resultId, payload }) => updateResult(jobId, resultId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.jobResults(jobId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.currentResult(jobId) });
    },
  });
}

export function useRestoreResultMutation(jobId) {
  return useMutation({
    mutationFn: (resultId) => restoreResult(jobId, resultId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.jobResults(jobId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.currentResult(jobId) });
    },
  });
}

/** Live chapter validation while typing (backend enforces it again on save). */
export function useValidateDescriptionMutation(jobId) {
  return useMutation({
    mutationFn: (description) => validateDescription(jobId, description),
  });
}
