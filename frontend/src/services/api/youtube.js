const API_BASE = '/api/v1/youtube';

export async function checkYouTubeAuthStatus() {
  const response = await fetch(`${API_BASE}/auth/status`);
  if (!response.ok) throw new Error('Failed to check YouTube auth status');
  return response.json();
}

export async function getYouTubeAuthUrl() {
  const response = await fetch(`${API_BASE}/auth/url`);
  if (!response.ok) throw new Error('Failed to get YouTube auth URL');
  return response.json();
}

export async function disconnectYouTube() {
  const response = await fetch(`${API_BASE}/auth/disconnect`, { method: 'POST' });
  if (!response.ok) throw new Error('Failed to disconnect YouTube');
  return response.json();
}

export async function listChannelVideos(maxResults = 50, pageToken = null) {
  const url = pageToken
    ? `${API_BASE}/videos?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/videos?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list videos');
  return response.json();
}

export async function listPlaylists(maxResults = 50, pageToken = null) {
  const url = pageToken
    ? `${API_BASE}/playlists?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/playlists?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list playlists');
  return response.json();
}

export async function listPlaylistItems(playlistId, maxResults = 50, pageToken = null) {
  const url = pageToken
    ? `${API_BASE}/playlists/${playlistId}/items?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/playlists/${playlistId}/items?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list playlist items');
  return response.json();
}

export async function publishToYouTube(formData) {
  const response = await fetch(`${API_BASE}/publish`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
}
