import { useMutation, useQuery } from '@tanstack/react-query';

import { QUERY_KEYS } from '../constants';
import {
  createTemplate,
  deleteTemplate,
  duplicateTemplate,
  getTemplate,
  getTemplateVariables,
  listTemplates,
  previewTemplate,
  updateTemplate,
} from '../services/api/promptTemplates';
import { queryClient } from './queryClient';

export function useTemplatesQuery() {
  return useQuery({ queryKey: QUERY_KEYS.templates, queryFn: listTemplates });
}

export function useTemplateQuery(templateId) {
  return useQuery({
    queryKey: QUERY_KEYS.template(templateId),
    queryFn: () => getTemplate(templateId),
    enabled: Boolean(templateId),
  });
}

export function useTemplateVariablesQuery() {
  return useQuery({
    queryKey: QUERY_KEYS.templateVariables,
    queryFn: getTemplateVariables,
    staleTime: 5 * 60_000,
  });
}

export function useCreateTemplateMutation() {
  return useMutation({
    mutationFn: createTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.templates }),
  });
}

export function useUpdateTemplateMutation() {
  return useMutation({
    mutationFn: ({ templateId, payload }) => updateTemplate(templateId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.templates });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.template(variables.templateId) });
    },
  });
}

export function useDeleteTemplateMutation() {
  return useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.templates }),
  });
}

export function useDuplicateTemplateMutation() {
  return useMutation({
    mutationFn: duplicateTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUERY_KEYS.templates }),
  });
}

export function usePreviewTemplateMutation() {
  return useMutation({
    mutationFn: ({ userPromptTemplate, sampleContext }) =>
      previewTemplate(userPromptTemplate, sampleContext),
  });
}
