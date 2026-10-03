import { useQuery } from '@tanstack/react-query';

import { QUERY_KEYS } from '../constants';
import { getModels, getQuota, getStorageUsage, getSystemStatus } from '../services/api/system';

export function useSystemStatusQuery(options = {}) {
  return useQuery({
    queryKey: QUERY_KEYS.systemStatus,
    queryFn: getSystemStatus,
    refetchInterval: 30_000,
    retry: 1,
    throwOnError: false,
    ...options,
  });
}

export function useModelsQuery() {
  return useQuery({
    queryKey: QUERY_KEYS.systemModels,
    queryFn: getModels,
    staleTime: 5 * 60_000,
  });
}

export function useQuotaQuery() {
  return useQuery({
    queryKey: QUERY_KEYS.systemQuota,
    queryFn: getQuota,
    refetchInterval: 20_000,
    throwOnError: false,
  });
}

export function useStorageQuery() {
  return useQuery({
    queryKey: QUERY_KEYS.systemStorage,
    queryFn: getStorageUsage,
    staleTime: 30_000,
  });
}
