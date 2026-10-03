import { apiClient, unwrap } from './client';

export async function getSystemStatus() {
  const response = await apiClient.get('/system/status');
  return unwrap(response);
}

export async function getModels() {
  const response = await apiClient.get('/system/models');
  return unwrap(response);
}

export async function getQuota() {
  const response = await apiClient.get('/system/quota');
  return unwrap(response);
}

export async function getStorageUsage() {
  const response = await apiClient.get('/system/storage');
  return unwrap(response);
}

export async function getHealth() {
  const response = await apiClient.get('/health');
  return unwrap(response);
}

export async function runCleanup() {
  const response = await apiClient.post('/system/cleanup');
  return unwrap(response);
}
