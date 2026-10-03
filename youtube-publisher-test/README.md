# YouTube Publisher - Test Sandbox

This is an isolated sandbox for testing the Phase 2 YouTube publishing flow before integrating it into the main application.

## Architecture

```
youtube-publisher-test/
├── backend/
│   ├── main.py              # FastAPI app with YouTube OAuth + publish endpoints
│   ├── requirements.txt     # Python dependencies
│   ├── client_secrets.json  # Google OAuth client secrets (MOCK - replace with real one)
│   └── run.bat              # Windows startup script
└── frontend/
    ├── src/
    │   ├── pages/PublishPage.jsx   # Publish form with demo data
    │   ├── services/api.js         # API client
    │   └── ...
    ├── package.json
    └── vite.config.js
```

## Prerequisites

- Python 3.12+ (main app uses 3.12.14)
- Node.js 18+
- Google Cloud Console project with YouTube Data API v3 enabled
- OAuth 2.0 client credentials (desktop app type)

## Quick Start

### 1. Start the Backend

```powershell
# From the backend directory
cd youtube-publisher-test\backend
..\..\backend\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

Or use the batch file:
```powershell
cd youtube-publisher-test\backend
.\run.bat
```

The backend will start at `http://127.0.0.1:8001`

### 2. Start the Frontend

```powershell
# From the frontend directory (new terminal)
cd youtube-publisher-test\frontend
npm run dev
```

The frontend will start at `http://localhost:3001`

### 3. Open the Publish Page

Navigate to: `http://localhost:3001/publish`

You should see:
- Pre-filled demo SEO data (title, description, tags, thumbnail prompt)
- A "Connect YouTube" button
- Form fields for Video ID, thumbnail upload, visibility
- A "Publish to YouTube" button

## Testing the Flow

### Step 1: Verify Backend Health

```powershell
curl http://127.0.0.1:8001/health
# Expected: {"status":"ok","service":"youtube-publisher"}
```

### Step 2: Check Auth Status

```powershell
curl http://127.0.0.1:8001/youtube/auth/status
# Expected: {"authorized":false,"message":"Not connected. Click Connect to authorize."}
```

### Step 3: Get OAuth URL

```powershell
curl http://127.0.0.1:8001/youtube/auth/url
# Expected: {"auth_url":"https://accounts.google.com/o/oauth2/auth?...","redirect_uri":"http://localhost:8001/youtube/auth/callback"}
```

### Step 4: Test Publish (Without Auth)

```powershell
.\backend\.venv\Scripts\python.exe test_publish.py
# Expected: {"success":false,"message":"Not authorized. Connect YouTube first.","data":null}
```

### Step 5: Complete OAuth Flow

1. Click "Connect YouTube" in the frontend
2. A Google OAuth consent screen will open
3. Sign in with your Google account and grant permissions
4. You'll be redirected back to the frontend with `?auth=success`
5. The status should now show "Connected"

### Step 6: Test Publish (With Auth)

1. Enter a YouTube Video ID (must be a video you own)
2. Optionally upload a thumbnail image
3. Select visibility (public/unlisted/private)
4. Click "Publish to YouTube"
5. The form data will be sent to the backend and YouTube API will update the video

## Data Flow

### Phase 1 → Phase 2 Handoff

The SEO data flows from Phase 1 (backend → frontend) to Phase 2 (frontend → backend → YouTube) via:

**Option A: URL Query Params (Recommended)**
```
Phase 1 Frontend: window.location.href = `/publish?title=...&description=...&tags=...&thumbnail_prompt=...`
Phase 2 Frontend: Reads URL params and pre-fills the form
```

**Option B: localStorage**
```
Phase 1 Frontend: localStorage.setItem('yt-publisher-seo-data', JSON.stringify({title, description, tags}))
Phase 2 Frontend: Reads from localStorage on load
```

**Option C: Manual Paste**
```
User copies SEO data from Phase 1 frontend
Pastes into Phase 2 frontend's JSON textarea
```

### Data Format (Matches Phase 1 Exactly)

```javascript
{
  title: "string",           // max 100 chars
  description: "string",     // max 5000 chars
  tags: ["string"],          // array of strings
  thumbnail_prompt: "string", // optional
  seo_score: 87,             // optional
  version_number: 1          // optional
}
```

## API Endpoints

### `GET /youtube/auth/status`
Returns whether the user is authorized.

**Response:**
```json
{
  "authorized": false,
  "message": "Not connected. Click Connect to authorize."
}
```

### `GET /youtube/auth/url`
Returns the Google OAuth consent URL.

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
  "redirect_uri": "http://localhost:8001/youtube/auth/callback"
}
```

### `GET /youtube/auth/callback?code=...&state=...`
Handles the OAuth redirect, saves the refresh token.

**Response:** Redirects to `http://localhost:3001/publish?auth=success`

### `POST /youtube/publish`
Updates a YouTube video with title, description, tags, and optionally a thumbnail.

**Request (multipart/form-data):**
```
title: string
description: string
tags: JSON array string (e.g., '["tag1", "tag2"]')
video_id: string
visibility: "public" | "unlisted" | "private"
thumbnail_prompt: string (optional)
thumbnail: file (optional)
```

**Success Response:**
```json
{
  "success": true,
  "message": "Published to YouTube successfully.",
  "data": {
    "video_id": "dQw4w9WgXcQ",
    "title": "Updated Title",
    "visibility": "public",
    "thumbnail_uploaded": true,
    "thumbnail_url": "https://..."
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Not authorized. Connect YouTube first.",
  "data": null
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `YOUTUBE_CLIENT_SECRETS_PATH` | `./client_secrets.json` | Path to Google OAuth client secrets |
| `YOUTUBE_TOKEN_DIR` | `~/.youtube-publisher-test` | Directory for storing OAuth tokens |
| `YOUTUBE_REDIRECT_URI` | `http://localhost:8001/youtube/auth/callback` | OAuth redirect URI |

### Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**
4. Go to **APIs & Services > Credentials**
5. Create **OAuth 2.0 Client ID** (Desktop app type)
6. Download the JSON file and save it as `client_secrets.json` in the backend directory
7. Update the `redirect_uris` in `client_secrets.json` to include:
   - `http://localhost:8001/youtube/auth/callback`

## Integration into Main Application

Once testing is complete, follow these steps to integrate into the main app:

### Backend Changes

1. Copy `youtube-publisher-test/backend/main.py` to `backend/app/api/v1/youtube.py`
2. Copy `youtube-publisher-test/backend/services/youtube_client.py` to `backend/app/services/youtube/`
3. Add to `backend/app/api/router.py`:
   ```python
   from app.api.v1 import youtube
   api_router.include_router(youtube.router)
   ```
4. Add to `backend/requirements.txt`:
   ```
   google-api-python-client==2.149.0
   google-auth-oauthlib==1.2.1
   google-auth-httplib2==0.2.0
   ```
5. Add environment variables to `.env`:
   ```env
   YOUTUBE_CLIENT_SECRETS_PATH=./client_secrets.json
   YOUTUBE_TOKEN_DIR=~/.youtube-publisher
   ```

### Frontend Changes

1. Copy `youtube-publisher-test/frontend/src/pages/PublishPage.jsx` to `frontend/src/pages/PublishPage.jsx`
2. Copy `youtube-publisher-test/frontend/src/services/api/publisher.js` to `frontend/src/services/api/publisher.js`
3. Add to `frontend/src/constants/index.js`:
   ```javascript
   publish: '/publish',
   ```
4. Add to `frontend/src/App.jsx`:
   ```jsx
   import PublishPage from './pages/PublishPage';
   // Add route: <Route path={ROUTES.publish} element={<PublishPage />} />
   ```
5. Add button to `frontend/src/components/seo/SeoOutputView.jsx`:
   ```jsx
   <Button
     variant="primary"
     onClick={() => {
       const params = new URLSearchParams({
         title: result.title,
         description: result.description,
         tags: (result.tags || []).join(','),
         thumbnail_prompt: result.thumbnail_prompt || '',
       });
       window.location.href = `/publish?${params}`;
     }}
   >
     Publish to YouTube
   </Button>
   ```

## Safety Guarantees

- **No Phase 1 code imports**: Phase 2 code is completely isolated
- **No database changes**: Phase 2 uses file-based token storage only
- **No Phase 1 settings**: Phase 2 uses its own `YOUTUBE_*` environment variables
- **Separate ports**: Phase 2 backend runs on 8001, Phase 1 on 8000
- **Separate frontend port**: Phase 2 frontend runs on 3001, Phase 1 on 8080
- **No shared state**: Phase 2 only depends on the SEO data passed via URL/localStorage

## Troubleshooting

### Backend won't start
- Ensure Python 3.12 is being used
- Check that `client_secrets.json` exists in the backend directory
- Verify port 8001 is not in use

### Frontend can't connect to backend
- Ensure backend is running on `http://127.0.0.1:8001`
- Check browser console for CORS errors
- Verify `import.meta.env.DEV` is `true` in development

### OAuth flow fails
- Verify `client_secrets.json` is valid
- Check that redirect URI in Google Cloud Console matches `YOUTUBE_REDIRECT_URI`
- Ensure YouTube Data API v3 is enabled in Google Cloud Console

### Publish fails with "Not authorized"
- Complete the OAuth flow first (click "Connect YouTube")
- Check that token file exists in `~/.youtube-publisher-test/`
- Verify the YouTube video ID is correct and you own the video

## Next Steps

1. Test the complete flow in this sandbox
2. Verify OAuth works with real Google credentials
3. Test publishing to a real YouTube video
4. Once confirmed working, follow the integration steps above
5. Remove the `youtube-publisher-test/` directory after integration
