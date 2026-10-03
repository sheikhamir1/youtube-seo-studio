const API_BASE = import.meta.env.DEV ? 'http://localhost:8001' : '/api';

export async function checkAuthStatus() {
  const response = await fetch(`${API_BASE}/youtube/auth/status`);
  if (!response.ok) throw new Error('Failed to check auth status');
  return response.json();
}

export async function getAuthUrl() {
  const response = await fetch(`${API_BASE}/youtube/auth/url`);
  if (!response.ok) throw new Error('Failed to get auth URL');
  return response.json();
}

export async function publishToYouTube(formData) {
  const response = await fetch(`${API_BASE}/youtube/publish`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
}
