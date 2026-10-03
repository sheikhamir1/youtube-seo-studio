import { QueryClient } from '@tanstack/react-query';

/**
 * Sensible defaults: server data is cached briefly, refetched on focus and
 * never retried more than twice. Processing pages use SSE instead of polling.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      gcTime: 5 * 60_000,
      retry: 2,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
