import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { checkAuthStatus, getAuthUrl, publishToYouTube } from '../services/api';

const DEMO_SEO_DATA = {
  title: '10 Tips for Better YouTube SEO in 2026',
  description:
    'In this video, I share 10 actionable tips to improve your YouTube SEO and get more views. From keyword research to thumbnail optimization, these strategies will help you rank higher and grow your channel.',
  tags: ['youtube seo', 'video marketing', 'youtube tips', 'seo 2026', 'content creation'],
  thumbnail_prompt:
    'A vibrant YouTube thumbnail with a magnifying glass over a play button, bold text "SEO TIPS", bright colors, high contrast, eye-catching design',
  seo_score: 87,
  version_number: 1,
};

const LS_KEY = 'yt-publisher-seo-data';

export default function PublishPage() {
  const [searchParams] = useSearchParams();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [authMessage, setAuthMessage] = useState('Checking connection...');
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [error, setError] = useState(null);

  // Form state - initialized from URL params, localStorage, or demo data
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState([]);
  const [thumbnailPrompt, setThumbnailPrompt] = useState('');
  const [videoId, setVideoId] = useState('');
  const [visibility, setVisibility] = useState('public');
  const [thumbnailFile, setThumbnailFile] = useState(null);

  // Load SEO data from URL params (from Phase 1) or localStorage or demo
  useEffect(() => {
    let data = null;

    // 1. Try URL params (handoff from Phase 1 frontend)
    const urlTitle = searchParams.get('title');
    const urlDesc = searchParams.get('description');
    const urlTags = searchParams.get('tags');
    const urlThumbPrompt = searchParams.get('thumbnail_prompt');

    if (urlTitle || urlDesc || urlTags) {
      data = {
        title: urlTitle || '',
        description: urlDesc || '',
        tags: urlTags ? urlTags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        thumbnail_prompt: urlThumbPrompt || '',
      };
    }

    // 2. Try localStorage (persisted handoff)
    if (!data) {
      try {
        const stored = localStorage.getItem(LS_KEY);
        if (stored) data = JSON.parse(stored);
      } catch {
        // ignore
      }
    }

    // 3. Fallback to demo data
    if (!data) {
      data = DEMO_SEO_DATA;
    }

    setTitle(data.title || '');
    setDescription(data.description || '');
    setTags(data.tags || []);
    setThumbnailPrompt(data.thumbnail_prompt || '');
  }, [searchParams]);

  // Save to localStorage whenever data changes
  useEffect(() => {
    if (title || description || tags.length) {
      const payload = { title, description, tags, thumbnail_prompt: thumbnailPrompt };
      localStorage.setItem(LS_KEY, JSON.stringify(payload));
    }
  }, [title, description, tags, thumbnailPrompt]);

  // Check auth status on mount
  useEffect(() => {
    checkAuthStatus()
      .then((res) => {
        setIsAuthorized(res.authorized);
        setAuthMessage(res.message);
      })
      .catch(() => {
        setIsAuthorized(false);
        setAuthMessage('Could not check auth status.');
      });
  }, []);

  const handleConnectYouTube = useCallback(async () => {
    try {
      const { auth_url } = await getAuthUrl();
      window.open(auth_url, '_blank', 'width=500,height=600');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const handlePublish = useCallback(async () => {
    if (!isAuthorized) {
      setError('Please connect your YouTube account first.');
      return;
    }
    if (!videoId.trim()) {
      setError('YouTube Video ID is required.');
      return;
    }

    setIsPublishing(true);
    setError(null);
    setPublishResult(null);

    try {
      const formData = new FormData();
      formData.append('title', title);
      formData.append('description', description);
      formData.append('tags', JSON.stringify(tags));
      formData.append('video_id', videoId.trim());
      formData.append('visibility', visibility);
      formData.append('thumbnail_prompt', thumbnailPrompt);
      if (thumbnailFile) {
        formData.append('thumbnail', thumbnailFile);
      }

      const result = await publishToYouTube(formData);
      setPublishResult(result);
    } catch (err) {
      setError(err.message || 'Failed to publish.');
    } finally {
      setIsPublishing(false);
    }
  }, [isAuthorized, title, description, tags, videoId, visibility, thumbnailPrompt, thumbnailFile]);

  const tagsInput = tags.join(', ');

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Publish to YouTube</h1>
          <p className="mt-1 text-sm text-gray-500">
            Auto-filled from SEO output. Connect your YouTube account and publish.
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
          {!isAuthorized && (
            <button
              type="button"
              onClick={handleConnectYouTube}
              className="mt-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Connect YouTube
            </button>
          )}
        </div>
      </header>

      <div className="grid gap-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-gray-500">{title.length}/100 characters</p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            maxLength={5000}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-gray-500">{description.length}/5000 characters</p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Tags (comma-separated)</label>
          <input
            type="text"
            value={tagsInput}
            onChange={(e) => setTags(e.target.value.split(',').map((t) => t.trim()).filter(Boolean))}
            placeholder="youtube, seo, marketing"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded border border-gray-200 bg-gray-100 px-2 py-0.5 text-xs text-gray-700"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Thumbnail Prompt</label>
          <input
            type="text"
            value={thumbnailPrompt}
            onChange={(e) => setThumbnailPrompt(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">YouTube Video ID</label>
          <input
            type="text"
            value={videoId}
            onChange={(e) => setVideoId(e.target.value)}
            placeholder="e.g. dQw4w9WgXcQ"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-gray-500">
            The ID of the already-uploaded video you want to update.
          </p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Thumbnail Image</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setThumbnailFile(e.target.files?.[0] || null)}
            className="block w-full text-sm text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
          />
          {thumbnailFile && (
            <p className="mt-1 text-xs text-gray-500">Selected: {thumbnailFile.name}</p>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Visibility</label>
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="public">Public</option>
            <option value="unlisted">Unlisted</option>
            <option value="private">Private</option>
          </select>
        </div>

        <button
          type="button"
          onClick={handlePublish}
          disabled={isPublishing}
          className="w-full rounded-md bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isPublishing ? 'Publishing...' : 'Publish to YouTube'}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <strong>Error:</strong> {error}
        </div>
      )}

      {publishResult && (
        <div className="rounded-md border border-green-200 bg-green-50 p-4 text-sm text-green-800">
          <h3 className="font-semibold">Publish Result</h3>
          <pre className="mt-2 overflow-auto rounded bg-white p-3 text-xs">
            {JSON.stringify(publishResult, null, 2)}
          </pre>
        </div>
      )}

      <div className="rounded-md border border-gray-200 bg-white p-4 text-xs text-gray-500 shadow-sm">
        <h3 className="font-semibold text-gray-700">Data Handoff (Phase 1 → Phase 2)</h3>
        <p className="mt-1">
          This form auto-fills from URL params (e.g. <code>/publish?title=...&description=...&tags=...&thumbnail_prompt=...</code>),
          localStorage, or the demo data below. In the real app, the Phase 1 frontend will link here with the
          generated SEO data pre-filled.
        </p>
        <div className="mt-3">
          <label className="mb-1 block font-medium text-gray-700">Paste JSON (simulating Phase 1 handoff):</label>
          <textarea
            rows={4}
            placeholder='Paste {"title":"...","description":"...","tags":["..."]}'
            onChange={(e) => {
              try {
                const data = JSON.parse(e.target.value);
                if (data.title) setTitle(data.title);
                if (data.description) setDescription(data.description);
                if (data.tags) setTags(Array.isArray(data.tags) ? data.tags : [data.tags]);
                if (data.thumbnail_prompt) setThumbnailPrompt(data.thumbnail_prompt);
              } catch {
                // ignore invalid JSON while typing
              }
            }}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-xs focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>
    </div>
  );
}
