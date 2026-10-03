import { apiClient, unwrap, unwrapMessage } from './client';

export async function listJobs({ page = 1, pageSize = 20, status = '', search = '', sort = '-created_at' } = {}) {
  const response = await apiClient.get('/jobs', {
    params: {
      page,
      page_size: pageSize,
      status: status || undefined,
      search: search || undefined,
      sort,
    },
  });
  return unwrap(response);
}

export async function getJob(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}`);
  return unwrap(response);
}

export async function getJobSummary(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/summary`);
  return unwrap(response);
}

export async function getJobChunks(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/chunks`);
  return unwrap(response);
}

export async function createJob(payload) {
  const response = await apiClient.post('/jobs', payload);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function getTimeline(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/timeline`);
  return unwrap(response);
}

export async function listJobEvents(jobId, { page = 1, pageSize = 200, level } = {}) {
  const response = await apiClient.get(`/jobs/${jobId}/events`, {
    params: { page, page_size: pageSize, level: level || undefined },
  });
  return unwrap(response);
}

export async function cancelJob(jobId) {
  const response = await apiClient.post(`/jobs/${jobId}/cancel`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function retryJob(jobId) {
  const response = await apiClient.post(`/jobs/${jobId}/retry`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function regenerateSeo(jobId, { promptTemplateId, selectedModel }) {
  const response = await apiClient.post(`/jobs/${jobId}/regenerate`, {
    prompt_template_id: promptTemplateId || null,
    selected_model: selectedModel || null,
  });
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function deleteJob(jobId) {
  const response = await apiClient.delete(`/jobs/${jobId}`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function getJobSourceInfo(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/source`);
  return unwrap(response);
}
