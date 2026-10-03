import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { checkAuthStatus, getAuthUrl, listChannelVideos, listPlaylists, listPlaylistItems, disconnect } from '../services/api';

const PRIVACY_COLORS = {
  public: 'bg-green-100 text-green-800',
  unlisted: 'bg-yellow-100 text-yellow-800',
  private: 'bg-red-100 text-red-800',
  unknown: 'bg-gray-100 text-gray-800',
};

export default function VideoSelectPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [authMessage, setAuthMessage] = useState('Checking connection...');
  const [view, setView] = useState(searchParams.get('view') || 'videos'); // 'videos' | 'playlists' | 'playlist-detail'
  const [playlistId, setPlaylistId] = useState(searchParams.get('playlist_id') || '');

  // Videos state
  const [videos, setVideos] = useState([]);
  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState('all');
  const [videoPageToken, setVideoPageToken] = useState(null);
  const [isLoadingVideos, setIsLoadingVideos] = useState(false);

  // Playlists state
  const [playlists, setPlaylists] = useState([]);
  const [isLoadingPlaylists, setIsLoadingPlaylists] = useState(false);
  const [playlistPageToken, setPlaylistPageToken] = useState(null);

  // Playlist detail state
  const [playlistVideos, setPlaylistVideos] = useState([]);
  const [playlistTitle, setPlaylistTitle] = useState('');
  const [isLoadingPlaylistItems, setIsLoadingPlaylistItems] = useState(false);
  const [playlistItemsPageToken, setPlaylistItemsPageToken] = useState(null);

  const [error, setError] = useState(null);

  useEffect(() => {
    checkAuthStatus()
      .then((res) => {
        setIsAuthorized(res.authorized);
        setAuthMessage(res.message);
        if (res.authorized) {
          if (view === 'playlists') {
            loadPlaylists();
          } else if (view === 'playlist-detail' && playlistId) {
            loadPlaylistItems(playlistId);
          } else {
            loadVideos();
          }
        }
      })
      .catch(() => {
        setIsAuthorized(false);
        setAuthMessage('Could not check auth status.');
      });
  }, []);

  const loadVideos = async (pageToken = null) => {
    setIsLoadingVideos(true);
    setError(null);
    try {
      const data = await listChannelVideos(50, pageToken);
      setChannels(data.channels || []);
      if (pageToken) {
        setVideos(prev => [...prev, ...(data.videos || [])]);
      } else {
        setVideos(data.videos || []);
      }
      setVideoPageToken(data.next_page_token || null);
      setSelectedChannel('all');
    } catch (err) {
      setError(err.message || 'Failed to load videos.');
    } finally {
      setIsLoadingVideos(false);
    }
  };

  const loadPlaylists = async (pageToken = null) => {
    setIsLoadingPlaylists(true);
    setError(null);
    try {
      const data = await listPlaylists(50, pageToken);
      if (pageToken) {
        setPlaylists(prev => [...prev, ...(data.playlists || [])]);
      } else {
        setPlaylists(data.playlists || []);
      }
      setPlaylistPageToken(data.next_page_token || null);
    } catch (err) {
      setError(err.message || 'Failed to load playlists.');
    } finally {
      setIsLoadingPlaylists(false);
    }
  };

  const loadPlaylistItems = async (pid, pageToken = null) => {
    setIsLoadingPlaylistItems(true);
    setError(null);
    try {
      const data = await listPlaylistItems(pid, 50, pageToken);
      if (pageToken) {
        setPlaylistVideos(prev => [...prev, ...(data.videos || [])]);
      } else {
        setPlaylistVideos(data.videos || []);
      }
      setPlaylistTitle(data.playlist_title || '');
      setPlaylistItemsPageToken(data.next_page_token || null);
      setPlaylistId(pid);
    } catch (err) {
      setError(err.message || 'Failed to load playlist items.');
    } finally {
      setIsLoadingPlaylistItems(false);
    }
  };

  const handleConnectYouTube = async () => {
    try {
      const { auth_url } = await getAuthUrl();
      window.open(auth_url, '_blank', 'width=500,height=600');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnect();
      setIsAuthorized(false);
      setAuthMessage('Disconnected. Click Connect to authorize a different account.');
      setVideos([]);
      setChannels([]);
      setPlaylists([]);
      setPlaylistVideos([]);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSelectVideo = (video) => {
    const params = new URLSearchParams({
      video_id: video.video_id,
      channel_title: video.channel_title,
    });
    navigate(`/publish?${params}`);
  };

  const showVideosView = () => {
    setView('videos');
    setSearchParams({ view: 'videos' });
    if (videos.length === 0) loadVideos();
  };

  const showPlaylistsView = () => {
    setView('playlists');
    setSearchParams({ view: 'playlists' });
    if (playlists.length === 0) loadPlaylists();
  };

  const showPlaylistDetail = (pid) => {
    setView('playlist-detail');
    setSearchParams({ view: 'playlist-detail', playlist_id: pid });
    loadPlaylistItems(pid);
  };

  const filteredVideos = videos.filter((v) => selectedChannel === 'all' || v.channel_id === selectedChannel);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Select Video</h1>
          <p className="mt-1 text-sm text-gray-500">
            Choose a video from your YouTube channel to update with SEO metadata.
          </p>
        </div>
        <div className="text-right">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
              isAuthorized ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
            }`}
          >
            {isAuthorized ? 'Connected' : 'Not connected'}
          </span>
          <p className="mt-1 text-xs text-gray-500">{authMessage}</p>
          <div className="mt-2 flex gap-2">
            {!isAuthorized ? (
              <button
                type="button"
                onClick={handleConnectYouTube}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Connect YouTube
              </button>
            ) : (
              <button
                type="button"
                onClick={handleDisconnect}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Switch Account
              </button>
            )}
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <strong>Error:</strong> {error}
        </div>
      )}

      {isAuthorized && (
        <div className="flex items-center gap-2 border-b border-gray-200">
          <button
            type="button"
            onClick={showVideosView}
            className={`px-4 py-2 text-sm font-medium ${
              view === 'videos'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Videos
          </button>
          <button
            type="button"
            onClick={showPlaylistsView}
            className={`px-4 py-2 text-sm font-medium ${
              view === 'playlists' || view === 'playlist-detail'
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Playlists
          </button>
          <div className="ml-auto">
            <button
              type="button"
              onClick={() => {
                const input = prompt('Paste YouTube video link or ID:');
                if (input) {
                  const trimmed = input.trim();
                  let videoId = trimmed;
                  if (trimmed.includes('youtu.be/') || trimmed.includes('youtube.com/watch')) {
                    try {
                      const url = new URL(trimmed);
                      videoId = url.searchParams.get('v') || trimmed.split('youtu.be/')[1]?.split('?')[0] || trimmed;
                    } catch {
                      videoId = trimmed.split('v=')[1]?.split('&')[0] || trimmed;
                    }
                  }
                   const params = new URLSearchParams({
                     video_id: videoId,
                     channel_title: 'Manual entry',
                   });
                   navigate(`/publish?${params}`);
                }
              }}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Enter Video ID Manually
            </button>
          </div>
        </div>
      )}

      {view === 'videos' && (
        <>
          {isAuthorized && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <p className="text-sm text-gray-600">
                  {filteredVideos.length > 0
                    ? `Showing ${filteredVideos.length} video${filteredVideos.length !== 1 ? 's' : ''} across ${channels.length} channel${channels.length !== 1 ? 's' : ''}.`
                    : 'No videos found.'}
                </p>
                {channels.length > 1 && (
                  <select
                    value={selectedChannel}
                    onChange={(e) => setSelectedChannel(e.target.value)}
                    className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                  >
                    <option value="all">All channels</option>
                    {channels.map((ch) => (
                      <option key={ch.channel_id} value={ch.channel_id}>
                        {ch.channel_title}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <button
                type="button"
                onClick={() => loadVideos()}
                disabled={isLoadingVideos}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoadingVideos ? 'Loading...' : 'Refresh'}
              </button>
            </div>
          )}

          {isLoadingVideos && (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="flex gap-4">
                    <div className="h-24 w-40 rounded-md bg-gray-200"></div>
                    <div className="flex-1 space-y-2">
                      <div className="h-4 rounded bg-gray-200"></div>
                      <div className="h-3 w-3/4 rounded bg-gray-200"></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!isLoadingVideos && filteredVideos.length === 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-8 text-center shadow-sm">
              <p className="text-sm text-gray-500">No videos found in your accessible channels.</p>
              <button
                type="button"
                onClick={() => {
                  const input = prompt('Paste YouTube video link or ID:');
                  if (input) {
                    const trimmed = input.trim();
                    let videoId = trimmed;
                    if (trimmed.includes('youtu.be/') || trimmed.includes('youtube.com/watch')) {
                      try {
                        const url = new URL(trimmed);
                        videoId = url.searchParams.get('v') || trimmed.split('youtu.be/')[1]?.split('?')[0] || trimmed;
                      } catch {
                        videoId = trimmed.split('v=')[1]?.split('&')[0] || trimmed;
                      }
                    }
                    const params = new URLSearchParams({
                      video_id: videoId,
                      title: 'Manual entry',
                      description: '',
                      channel_title: 'Manual entry',
                    });
                    navigate(`/publish?${params}`);
                  }
                }}
                className="mt-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                Enter Video ID Manually
              </button>
            </div>
          )}

          <div className="grid gap-4">
            {filteredVideos.map((video) => (
              <button
                key={video.video_id}
                type="button"
                onClick={() => handleSelectVideo(video)}
                className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md"
              >
                <div className="flex gap-4">
                  {video.thumbnail_url ? (
                    <img
                      src={video.thumbnail_url}
                      alt={video.title}
                      className="h-24 w-40 rounded-md object-cover"
                    />
                  ) : (
                    <div className="flex h-24 w-40 items-center justify-center rounded-md bg-gray-100 text-xs text-gray-400">
                      No thumbnail
                    </div>
                  )}
                  <div className="flex-1">
                    <h3 className="text-sm font-medium text-gray-900 line-clamp-2">{video.title}</h3>
                    <p className="mt-1 text-xs font-medium text-blue-600">{video.channel_title}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                      {video.description || 'No description'}
                    </p>
                    <div className="mt-2 flex items-center gap-2">
                      <span className={`mono rounded px-2 py-0.5 text-xs font-medium ${PRIVACY_COLORS[video.privacy_status] || PRIVACY_COLORS.unknown}`}>
                        {video.privacy_status || 'unknown'}
                      </span>
                      <span className="mono rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                        ID: {video.video_id}
                      </span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {videoPageToken && (
            <div className="flex justify-center">
              <button
                type="button"
                onClick={() => loadVideos(videoPageToken)}
                disabled={isLoadingVideos}
                className="rounded-md border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Load More
              </button>
            </div>
          )}
        </>
      )}

      {view === 'playlists' && (
        <>
          {isLoadingPlaylists ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="flex gap-4">
                    <div className="h-24 w-40 rounded-md bg-gray-200"></div>
                    <div className="flex-1 space-y-2">
                      <div className="h-4 rounded bg-gray-200"></div>
                      <div className="h-3 w-3/4 rounded bg-gray-200"></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-4">
                {playlists.map((playlist) => (
                  <button
                    key={playlist.playlist_id}
                    type="button"
                    onClick={() => showPlaylistDetail(playlist.playlist_id)}
                    className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md"
                  >
                    <div className="flex gap-4">
                      {playlist.thumbnail_url ? (
                        <img
                          src={playlist.thumbnail_url}
                          alt={playlist.title}
                          className="h-24 w-40 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-24 w-40 items-center justify-center rounded-md bg-gray-100 text-xs text-gray-400">
                          No thumbnail
                        </div>
                      )}
                      <div className="flex-1">
                        <h3 className="text-sm font-medium text-gray-900 line-clamp-2">{playlist.title}</h3>
                        <p className="mt-1 line-clamp-2 text-xs text-gray-500">
                          {playlist.description || 'No description'}
                        </p>
                        <p className="mt-2 text-xs text-gray-600">
                          {playlist.video_count} video{playlist.video_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              {playlistPageToken && (
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => loadPlaylists(playlistPageToken)}
                    disabled={isLoadingPlaylists}
                    className="rounded-md border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Load More
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {view === 'playlist-detail' && (
        <>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={showPlaylistsView}
              className="text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              ← Back to Playlists
            </button>
          </div>

          <h2 className="mt-4 text-lg font-semibold text-gray-900">{playlistTitle}</h2>

          {isLoadingPlaylistItems ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="flex gap-4">
                    <div className="h-24 w-40 rounded-md bg-gray-200"></div>
                    <div className="flex-1 space-y-2">
                      <div className="h-4 rounded bg-gray-200"></div>
                      <div className="h-3 w-3/4 rounded bg-gray-200"></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <>
              <div className="grid gap-4">
                {playlistVideos.map((video) => (
                  <button
                    key={video.video_id}
                    type="button"
                    onClick={() => handleSelectVideo(video)}
                    className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md"
                  >
                    <div className="flex gap-4">
                      {video.thumbnail_url ? (
                        <img
                          src={video.thumbnail_url}
                          alt={video.title}
                          className="h-24 w-40 rounded-md object-cover"
                        />
                      ) : (
                        <div className="flex h-24 w-40 items-center justify-center rounded-md bg-gray-100 text-xs text-gray-400">
                          No thumbnail
                        </div>
                      )}
                       <div className="flex-1">
                         <h3 className="text-sm font-medium text-gray-900 line-clamp-2">{video.title}</h3>
                         <p className="mt-1 text-xs text-gray-500">
                           Position: {video.position + 1}
                         </p>
                         <div className="mt-2 flex items-center gap-2">
                           <span className={`mono rounded px-2 py-0.5 text-xs font-medium ${PRIVACY_COLORS[video.privacy_status] || PRIVACY_COLORS.unknown}`}>
                             {video.privacy_status || 'unknown'}
                           </span>
                           <span className="mono rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                             ID: {video.video_id}
                           </span>
                         </div>
                       </div>
                    </div>
                  </button>
                ))}
              </div>

              {playlistItemsPageToken && (
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => loadPlaylistItems(playlistId, playlistItemsPageToken)}
                    disabled={isLoadingPlaylistItems}
                    className="rounded-md border border-gray-300 bg-white px-6 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Load More
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
