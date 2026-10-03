import { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import {
  checkYouTubeAuthStatus,
  getYouTubeAuthUrl,
  publishToYouTube,
  disconnectYouTube,
} from '../services/api/youtube';
import Button from '../components/ui/Button';

const DEMO_SEO_DATA = {
  title: '10 Tips for Better YouTube SEO in 2026',
  description:
    'In this video, I share 10 actionable tips to improve your YouTube SEO and get more views. From keyword research to thumbnail optimization, these strategies will help you rank higher and grow your channel.',
  tags: ['youtube seo', 'video marketing', 'youtube tips', 'seo 2026', 'content creation'],
};

const LS_KEY = 'yt-publisher-seo-data';

export default function PublishPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [authMessage, setAuthMessage] = useState('Checking YouTube authorization...');
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [error, setError] = useState(null);
  const [seoSource, setSeoSource] = useState('');

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState([]);
  const [tagsText, setTagsText] = useState('');
  const [videoId, setVideoId] = useState('');
  const [channelTitle, setChannelTitle] = useState('');
  const [visibility, setVisibility] = useState('private');
  const [thumbnailFile, setThumbnailFile] = useState(null);
  const [thumbnailPreview, setThumbnailPreview] = useState(null);

  // Load SEO data from URL params (handoff from JobDetailPage) or localStorage or demo - only on mount
  useEffect(() => {
    let data = null;

    const urlTitle = searchParams.get('title');
    const urlDesc = searchParams.get('description');
    const urlTags = searchParams.get('tags');

    if (urlTitle || urlDesc || urlTags) {
      data = {
        title: urlTitle || '',
        description: urlDesc || '',
        tags: urlTags
          ? urlTags
              .split(',')
              .map((t) => t.trim())
              .filter(Boolean)
          : [],
      };
      setSeoSource('url');
    }

    if (!data) {
      try {
        const stored = localStorage.getItem(LS_KEY);
        if (stored) {
          data = JSON.parse(stored);
          setSeoSource('localStorage');
        }
      } catch {
        // ignore
      }
    }

    if (!data) {
      data = DEMO_SEO_DATA;
      setSeoSource('demo');
    }

    setTitle(data.title || '');
    setDescription(data.description || '');
    setTags(data.tags || []);
    setTagsText((data.tags || []).join(', '));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Update video ID when selected from video list (without overwriting SEO data)
  useEffect(() => {
    const urlVideoId = searchParams.get('video_id');
    const urlChannelTitle = searchParams.get('channel_title');

    if (urlVideoId) {
      setVideoId(urlVideoId);
    }

    if (urlChannelTitle) {
      setChannelTitle(urlChannelTitle);
    }
  }, [searchParams]);

  // Save to localStorage whenever data changes
  useEffect(() => {
    if (title || description || tags.length) {
      const payload = { title, description, tags };
      localStorage.setItem(LS_KEY, JSON.stringify(payload));
    }
  }, [title, description, tags]);

  // Check auth status on mount
  useEffect(() => {
    checkYouTubeAuthStatus()
      .then((res) => {
        setIsAuthorized(res.authorized);
        setAuthMessage(res.message);
      })
      .catch(() => {
        setIsAuthorized(false);
        setAuthMessage('Could not check YouTube authorization.');
      });
  }, []);

  const handleConnectYouTube = useCallback(async () => {
    try {
      const { auth_url } = await getYouTubeAuthUrl();
      window.open(auth_url, '_blank', 'width=500,height=600');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const handleDisconnect = useCallback(async () => {
    try {
      await disconnectYouTube();
      setIsAuthorized(false);
      setAuthMessage('Disconnected. Click Connect to authorize a different account.');
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const compressImage = (file) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const maxWidth = 1280;
          const maxHeight = 720;
          let width = img.width;
          let height = img.height;

          if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width = Math.round(width * ratio);
            height = Math.round(height * ratio);
          }

          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          canvas.toBlob(
            (blob) => {
              if (!blob) {
                reject(new Error('Image compression failed.'));
                return;
              }
              const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, '') + '.jpg', {
                type: 'image/jpeg',
              });
              resolve(compressedFile);
            },
            'image/jpeg',
            0.85,
          );
        };
        img.onerror = () => reject(new Error('Failed to load image for compression.'));
        img.src = e.target.result;
      };
      reader.onerror = () => reject(new Error('Failed to read file.'));
      reader.readAsDataURL(file);
    });
  };

  const handleThumbnailChange = async (e) => {
    const file = e.target.files?.[0] || null;
    if (!file) {
      setThumbnailFile(null);
      setThumbnailPreview(null);
      return;
    }

    try {
      let processedFile = file;
      if (file.size > 2 * 1024 * 1024) {
        processedFile = await compressImage(file);
      }
      setThumbnailFile(processedFile);
      const reader = new FileReader();
      reader.onloadend = () => setThumbnailPreview(reader.result);
      reader.readAsDataURL(processedFile);
    } catch (err) {
      setError(err.message || 'Failed to process thumbnail.');
      setThumbnailFile(null);
      setThumbnailPreview(null);
    }
  };

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
  }, [isAuthorized, title, description, tags, videoId, visibility, thumbnailFile]);

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <header className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" icon={ArrowLeft} onClick={() => navigate(`/jobs/${jobId}`)}>
              Back
            </Button>
            <h1 className="text-2xl font-bold text-content">Publish to YouTube</h1>
          </div>
          <p className="mt-1 text-sm text-muted">
            Auto-filled from SEO output. Connect your YouTube account and publish.
            {seoSource && <span className="ml-2 text-xs text-muted">(from {seoSource})</span>}
          </p>
        </div>
        <div className="text-right">
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
              isAuthorized ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
            }`}
          >
            {isAuthorized ? 'YouTube API: Connected' : 'YouTube API: Not connected'}
          </span>
          <p className="mt-1 text-xs text-muted">{authMessage}</p>
          {!isAuthorized ? (
            <button
              type="button"
              onClick={handleConnectYouTube}
              className="mt-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              Connect YouTube
            </button>
          ) : (
            <button
              type="button"
              onClick={handleDisconnect}
              className="mt-2 rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-content hover:bg-surface-2"
            >
              Switch Account
            </button>
          )}
        </div>
      </header>

      {videoId && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800">
          <strong>Selected Video:</strong> {channelTitle ? `${channelTitle} - ` : ''}
          {videoId}{' '}
          <Link to={`/jobs/${jobId}/publish-youtube/videos`} className="underline">
            Change
          </Link>
        </div>
      )}

      {!videoId && (
        <div className="rounded-md border border-border bg-surface p-4 text-sm shadow-sm">
          <p className="text-muted">
            No video selected.{' '}
            <Link
              to={`/jobs/${jobId}/publish-youtube/videos`}
              className="font-medium text-blue-600 underline"
            >
              Select a video from your channel
            </Link>{' '}
            or{' '}
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
                      videoId =
                        url.searchParams.get('v') || trimmed.split('youtu.be/')[1]?.split('?')[0] || trimmed;
                    } catch {
                      videoId = trimmed.split('v=')[1]?.split('&')[0] || trimmed;
                    }
                  }
                  setVideoId(videoId);
                  setChannelTitle('Manual entry');
                }
              }}
              className="font-medium text-blue-600 underline"
            >
              enter manually
            </button>
            .
          </p>
        </div>
      )}

      <div className="grid gap-6 rounded-lg border border-border bg-surface p-6 shadow-sm">
        <div>
          <label className="mb-1 block text-sm font-medium text-white">Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={100}
            className="w-full rounded-md border border-border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-muted">{title.length}/100 characters</p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-content">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            maxLength={5000}
            className="w-full rounded-md border border-border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <p className="mt-1 text-xs text-muted">{description.length}/5000 characters</p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-content">Tags (comma-separated)</label>
          <input
            type="text"
            value={tagsText}
            onChange={(e) => {
              const text = e.target.value;
              setTagsText(text);
              setTags(
                text
                  .split(',')
                  .map((t) => t.trim())
                  .filter(Boolean),
              );
            }}
            placeholder="youtube, seo, marketing"
            className="w-full rounded-md border border-border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.map((tag) => (
              <span
                key={tag}
                className="rounded border border-border bg-surface-2 px-2 py-0.5 text-xs text-content"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-content">Thumbnail Image</label>
          <input
            type="file"
            accept="image/*"
            onChange={handleThumbnailChange}
            className="block w-full text-sm text-muted file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
          />
          {thumbnailFile && <p className="mt-1 text-xs text-muted">Selected: {thumbnailFile.name}</p>}
          {thumbnailPreview && (
            <div className="mt-3">
              <img
                src={thumbnailPreview}
                alt="Thumbnail preview"
                className="h-32 w-48 rounded-md border border-border object-cover"
              />
            </div>
          )}
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-content">Visibility</label>
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value)}
            className="w-full rounded-md border border-border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="private">Private</option>
            <option value="public">Public</option>
            <option value="unlisted">Unlisted</option>
          </select>
        </div>

        <button
          type="button"
          onClick={handlePublish}
          disabled={isPublishing || !videoId}
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
          <pre className="mt-2 overflow-auto rounded bg-surface p-3 text-xs">
            {JSON.stringify(publishResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
