import { apiClient, unwrap, unwrapMessage } from './client';

export async function listTemplates() {
  const response = await apiClient.get('/prompt-templates');
  return unwrap(response);
}

export async function getTemplate(templateId) {
  const response = await apiClient.get(`/prompt-templates/${templateId}`);
  return unwrap(response);
}

export async function createTemplate(payload) {
  const response = await apiClient.post('/prompt-templates', payload);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function updateTemplate(templateId, payload) {
  const response = await apiClient.patch(`/prompt-templates/${templateId}`, payload);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function deleteTemplate(templateId) {
  const response = await apiClient.delete(`/prompt-templates/${templateId}`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function duplicateTemplate(templateId) {
  const response = await apiClient.post(`/prompt-templates/${templateId}/duplicate`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function getTemplateVariables() {
  const response = await apiClient.get('/prompt-templates/variables');
  return unwrap(response);
}

/** Renders the template with sample data - never calls Gemini. */
export async function previewTemplate(userPromptTemplate, sampleContext) {
  const response = await apiClient.post('/prompt-templates/preview', {
    user_prompt_template: userPromptTemplate,
    sample_context: sampleContext || null,
  });
  return unwrap(response);
}
