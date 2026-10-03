import { apiClient, unwrap, unwrapMessage } from './client';

export async function createUploadSession({ filename, contentType, sizeBytes, chunkSizeBytes }) {
  const response = await apiClient.post('/uploads', {
    filename,
    content_type: contentType || null,
    size_bytes: sizeBytes,
    chunk_size_bytes: chunkSizeBytes,
  });
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function getUploadSession(uploadId) {
  const response = await apiClient.get(`/uploads/${uploadId}`);
  return unwrap(response);
}

/**
 * Upload one part as raw binary. `onUploadProgress` reports real browser
 * progress; `signal` allows pausing/cancelling a part in flight.
 */
export async function uploadPart({ uploadId, partNumber, blob, signal, onUploadProgress }) {
  const response = await apiClient.put(`/uploads/${uploadId}/parts/${partNumber}`, blob, {
    headers: { 'Content-Type': 'application/octet-stream' },
    signal,
    timeout: 0,
    onUploadProgress,
  });
  return unwrap(response);
}

export async function completeUpload(uploadId, sizeBytes) {
  const response = await apiClient.post(`/uploads/${uploadId}/complete`, {
    size_bytes: sizeBytes ?? null,
  });
  return { data: unwrap(response), message: unwrapMessage(response) };
}

export async function abortUpload(uploadId) {
  const response = await apiClient.delete(`/uploads/${uploadId}`);
  return unwrap(response);
}

export async function getPartSizeConfig() {
  const response = await apiClient.get('/uploads/config/part-size');
  return unwrap(response);
}
