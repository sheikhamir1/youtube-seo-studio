const API_BASE = 'http://localhost:8001';

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

export async function listChannelVideos(maxResults = 50, pageToken = null) {
  const url = pageToken 
    ? `${API_BASE}/youtube/videos?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/youtube/videos?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list videos');
  return response.json();
}

export async function listPlaylists(maxResults = 50, pageToken = null) {
  const url = pageToken
    ? `${API_BASE}/youtube/playlists?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/youtube/playlists?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list playlists');
  return response.json();
}

export async function listPlaylistItems(playlistId, maxResults = 50, pageToken = null) {
  const url = pageToken
    ? `${API_BASE}/youtube/playlists/${playlistId}/items?max_results=${maxResults}&page_token=${pageToken}`
    : `${API_BASE}/youtube/playlists/${playlistId}/items?max_results=${maxResults}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to list playlist items');
  return response.json();
}

export async function disconnect() {
  const response = await fetch(`${API_BASE}/youtube/auth/disconnect`, { method: 'POST' });
  if (!response.ok) throw new Error('Failed to disconnect');
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
