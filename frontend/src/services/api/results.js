import { apiClient, unwrap, unwrapMessage } from './client';

export async function listResults(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/results`);
  return unwrap(response);
}

export async function getCurrentResult(jobId) {
  const response = await apiClient.get(`/jobs/${jobId}/results/current`);
  return unwrap(response);
}

export async function getResult(jobId, resultId) {
  const response = await apiClient.get(`/jobs/${jobId}/results/${resultId}`);
  return unwrap(response);
}

export async function updateResult(jobId, resultId, payload) {
  const response = await apiClient.patch(`/jobs/${jobId}/results/${resultId}`, payload);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function restoreResult(jobId, resultId) {
  const response = await apiClient.post(`/jobs/${jobId}/results/${resultId}/restore`);
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function validateDescription(jobId, description) {
  const response = await apiClient.post(`/jobs/${jobId}/results/validate`, { description });
  return unwrap(response);
}
