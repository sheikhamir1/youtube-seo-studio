"""YouTube Publisher - isolated sandbox for Phase 2."""

from __future__ import annotations

import os
import json
import pathlib
from typing import Optional

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.responses import Response

# Google imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io


app = FastAPI(title="YouTube Publisher", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3002", "http://127.0.0.1:3001", "http://127.0.0.1:3002"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# Token storage path (outside container via volume mount in real setup)
TOKEN_DIR = pathlib.Path(os.environ.get("YOUTUBE_TOKEN_DIR", os.path.expanduser("~/.youtube-publisher-test")))
TOKEN_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = TOKEN_DIR / "token.json"

# OAuth client secrets path
CLIENT_SECRETS_PATH = os.environ.get("YOUTUBE_CLIENT_SECRETS_PATH", "./client_secrets.json")


# ---------------------------------------------------------------------------
# Schemas (matching Phase 1 data shape exactly)
# ---------------------------------------------------------------------------
class PublishRequest(BaseModel):
    title: str
    description: str
    tags: list[str]
    video_id: str
    visibility: str = "public"
    thumbnail_prompt: str = ""


class AuthStatusResponse(BaseModel):
    authorized: bool
    message: str


class PublishResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


class VideoItem(BaseModel):
    video_id: str
    title: str
    description: str
    thumbnail_url: Optional[str]
    privacy_status: str
    channel_id: str
    channel_title: str


class VideoListResponse(BaseModel):
    channels: list[dict]
    videos: list[VideoItem]
    next_page_token: Optional[str] = None


class PlaylistItem(BaseModel):
    playlist_id: str
    title: str
    description: str
    video_count: int
    thumbnail_url: Optional[str]


class PlaylistListResponse(BaseModel):
    playlists: list[PlaylistItem]
    next_page_token: Optional[str] = None


class PlaylistVideoItem(BaseModel):
    video_id: str
    title: str
    description: str
    thumbnail_url: Optional[str]
    position: int
    privacy_status: str = "unknown"


class PlaylistVideoListResponse(BaseModel):
    playlist_id: str
    playlist_title: str
    videos: list[PlaylistVideoItem]
    next_page_token: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def _load_credentials() -> Optional[Credentials]:
    if not TOKEN_PATH.exists():
        return None
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        info = json.load(f)
    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def _save_credentials(creds: Credentials) -> None:
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())


def _get_youtube_service():
    creds = _load_credentials()
    if not creds or not creds.valid:
        raise HTTPException(status_code=401, detail="Not authorized. Connect YouTube first.")
    return build("youtube", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/youtube/auth/status")
async def auth_status() -> AuthStatusResponse:
    creds = _load_credentials()
    if creds and creds.valid:
        return AuthStatusResponse(authorized=True, message="YouTube account connected.")
    return AuthStatusResponse(authorized=False, message="YouTube API not connected yet. Click Connect to authorize.")


@app.post("/youtube/auth/disconnect")
async def disconnect() -> JSONResponse:
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
    return JSONResponse({"success": True, "message": "Disconnected successfully."})


@app.get("/youtube/auth/url")
async def get_auth_url() -> JSONResponse:
    if not os.path.exists(CLIENT_SECRETS_PATH):
        raise HTTPException(
            status_code=500,
            detail=(
                "Google OAuth client_secrets.json not found. "
                f"Expected at: {CLIENT_SECRETS_PATH}. "
                "Download it from Google Cloud Console > APIs & Services > Credentials."
            ),
        )
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_PATH, scopes=SCOPES)
    # Use a fixed redirect URI for local testing
    redirect_uri = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8001/youtube/auth/callback")
    flow.redirect_uri = redirect_uri
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # Store state temporarily (in production use a session store)
    state_path = TOKEN_DIR / "auth_state.txt"
    state_path.write_text(state, encoding="utf-8")
    return JSONResponse({"auth_url": auth_url, "redirect_uri": redirect_uri})


@app.get("/youtube/auth/callback")
async def auth_callback(code: str, state: str) -> RedirectResponse:
    state_path = TOKEN_DIR / "auth_state.txt"
    if not state_path.exists():
        raise HTTPException(status_code=400, detail="No auth state found. Start auth flow again.")
    expected_state = state_path.read_text(encoding="utf-8").strip()
    if state != expected_state:
        raise HTTPException(status_code=400, detail="State mismatch. Possible CSRF attack.")
    state_path.unlink(missing_ok=True)

    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_PATH, scopes=SCOPES)
    redirect_uri = os.environ.get("YOUTUBE_REDIRECT_URI", "http://localhost:8001/youtube/auth/callback")
    flow.redirect_uri = redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_credentials(creds)
    # In real setup, redirect to frontend. For testing, return JSON.
    return RedirectResponse(url="http://localhost:3001/publish?auth=success")


@app.get("/youtube/videos", response_model=VideoListResponse)
async def list_channel_videos(max_results: int = 50, page_token: Optional[str] = None):
    """List videos from all channels the authenticated user manages."""
    try:
        youtube = _get_youtube_service()
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail=str(exc.detail)) from exc

    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails,snippet").execute()
        channels = channels_response.get("items", [])
        print(f"[youtube/videos] Found {len(channels)} channels: {[c['snippet']['title'] for c in channels]}")
        
        if not channels:
            return VideoListResponse(channels=[], videos=[])

        channel_summaries = []
        all_videos = []

        for channel in channels:
            channel_id = channel["id"]
            channel_title = channel["snippet"]["title"]
            uploads_playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]

            channel_summaries.append({
                "channel_id": channel_id,
                "channel_title": channel_title,
            })

            playlist_response = (
                youtube.playlistItems()
                .list(playlistId=uploads_playlist_id, part="snippet,contentDetails", maxResults=max_results, pageToken=page_token or "")
                .execute()
            )

            video_ids = []
            for item in playlist_response.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
                if not video_id:
                    continue
                video_ids.append(video_id)

            if video_ids:
                videos_response = (
                    youtube.videos()
                    .list(id=",".join(video_ids), part="snippet,status")
                    .execute()
                )
                privacy_map = {v["id"]: v["status"]["privacyStatus"] for v in videos_response.get("items", [])}

                for vid in video_ids:
                    snippet = next((i["snippet"] for i in playlist_response.get("items", []) if (i.get("contentDetails", {}).get("videoId") or i.get("snippet", {}).get("resourceId", {}).get("videoId")) == vid), {})
                    all_videos.append(
                        VideoItem(
                            video_id=vid,
                            title=snippet.get("title", "Untitled"),
                            description=snippet.get("description", ""),
                            thumbnail_url=snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                            privacy_status=privacy_map.get(vid, "unknown"),
                            channel_id=channel_id,
                            channel_title=channel_title,
                        )
                    )

        return VideoListResponse(
            channels=channel_summaries,
            videos=all_videos,
            next_page_token=playlist_response.get("nextPageToken"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list videos: {exc}") from exc


@app.get("/youtube/playlists", response_model=PlaylistListResponse)
async def list_playlists(max_results: int = 50, page_token: Optional[str] = None):
    """List all playlists for the authenticated user's channel."""
    try:
        youtube = _get_youtube_service()
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail=str(exc.detail)) from exc

    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
        channels = channels_response.get("items", [])
        if not channels:
            return PlaylistListResponse(playlists=[])

        uploads_playlist_id = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        playlists_response = (
            youtube.playlists()
            .list(mine=True, part="snippet,contentDetails", maxResults=max_results, pageToken=page_token or "")
            .execute()
        )

        playlists = []
        for item in playlists_response.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            playlists.append(
                PlaylistItem(
                    playlist_id=item["id"],
                    title=snippet.get("title", "Untitled"),
                    description=snippet.get("description", ""),
                    video_count=content_details.get("itemCount", 0),
                    thumbnail_url=snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                )
            )

        return PlaylistListResponse(
            playlists=playlists,
            next_page_token=playlists_response.get("nextPageToken"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list playlists: {exc}") from exc


@app.get("/youtube/playlists/{playlist_id}/items", response_model=PlaylistVideoListResponse)
async def list_playlist_items(playlist_id: str, max_results: int = 50, page_token: Optional[str] = None):
    """List videos in a specific playlist."""
    try:
        youtube = _get_youtube_service()
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail=str(exc.detail)) from exc

    try:
        playlist_response = (
            youtube.playlistItems()
            .list(playlistId=playlist_id, part="snippet,contentDetails", maxResults=max_results, pageToken=page_token or "")
            .execute()
        )

        playlist_title = ""
        video_ids = []
        playlist_videos = []
        for item in playlist_response.get("items", []):
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                continue
            if not playlist_title:
                playlist_title = snippet.get("playlistId", playlist_id)
            video_ids.append(video_id)
            playlist_videos.append({
                "video_id": video_id,
                "title": snippet.get("title", "Untitled"),
                "description": snippet.get("description", ""),
                "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
                "position": snippet.get("position", 0),
            })

        privacy_map = {}
        if video_ids:
            videos_response = (
                youtube.videos()
                .list(id=",".join(video_ids), part="status")
                .execute()
            )
            privacy_map = {v["id"]: v["status"].get("privacyStatus", "unknown") for v in videos_response.get("items", [])}

        videos = [
            PlaylistVideoItem(
                video_id=item["video_id"],
                title=item["title"],
                description=item["description"],
                thumbnail_url=item["thumbnail_url"],
                position=item["position"],
                privacy_status=privacy_map.get(item["video_id"], "unknown"),
            )
            for item in playlist_videos
        ]

        return PlaylistVideoListResponse(
            playlist_id=playlist_id,
            playlist_title=playlist_title,
            videos=videos,
            next_page_token=playlist_response.get("nextPageToken"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list playlist items: {exc}") from exc


@app.post("/youtube/publish")
async def publish_to_youtube(
    title: str = Form(...),
    description: str = Form(...),
    tags: str = Form(...),  # JSON array string from frontend
    video_id: str = Form(...),
    visibility: str = Form(default="public"),
    thumbnail_prompt: str = Form(default=""),
    thumbnail: Optional[UploadFile] = File(default=None),
) -> PublishResponse:
    try:
        youtube = _get_youtube_service()
    except HTTPException as exc:
        return PublishResponse(success=False, message=str(exc.detail))

    # Parse tags from JSON string (sent as JSON.stringify from frontend)
    try:
        tags_list = json.loads(tags) if tags else []
        if not isinstance(tags_list, list):
            tags_list = [str(tags_list)]
    except json.JSONDecodeError:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Validate visibility
    if visibility not in ("public", "unlisted", "private"):
        visibility = "public"

    # 1. Update video metadata (title, description, tags, visibility)
    video_body = {
        "id": video_id,
        "snippet": {
            "title": title[:100],  # YouTube title limit
            "description": description[:5000],  # YouTube description limit
            "tags": tags_list[:500],  # YouTube allows up to 500 chars, but we'll cap count
            "categoryId": "28",  # Science & Technology (default, can be made configurable)
        },
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": False,
        },
    }

    try:
        update_response = youtube.videos().update(
            part="snippet,status",
            body=video_body,
        ).execute()
    except Exception as exc:
        return PublishResponse(success=False, message=f"YouTube API error (videos.update): {exc}")

    # 2. Upload thumbnail if provided
    thumbnail_url = None
    if thumbnail and thumbnail.filename:
        try:
            thumbnail.file.seek(0)
            thumbnail_bytes = await thumbnail.read()
            if len(thumbnail_bytes) > 50 * 1024 * 1024:
                return PublishResponse(
                    success=False,
                    message=f"Thumbnail upload failed: file size is {len(thumbnail_bytes) / 1024 / 1024:.1f}MB, max is 50MB.",
                    data={"video_id": video_id, "title": title, "thumbnail_uploaded": False},
                )
            content_type = (thumbnail.content_type or "").lower()
            if content_type not in {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}:
                return PublishResponse(
                    success=False,
                    message=f"Thumbnail upload failed: unsupported content type {thumbnail.content_type}.",
                    data={"video_id": video_id, "title": title, "thumbnail_uploaded": False},
                )
            thumbnail_body = MediaIoBaseUpload(
                io.BytesIO(thumbnail_bytes),
                mimetype=thumbnail.content_type or "image/png",
                resumable=True,
            )
            thumb_response = youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumbnail_body,
            ).execute()
            print(f"[youtube/publish] thumbnails.set response keys: {list(thumb_response.keys())}")
            thumbnail_url = (
                thumb_response.get("default", {}).get("url")
                or thumb_response.get("medium", {}).get("url")
                or thumb_response.get("high", {}).get("url")
                or thumb_response.get("standard", {}).get("url")
                or thumb_response.get("maxres", {}).get("url")
            )
            print(f"[youtube/publish] resolved thumbnail_url: {thumbnail_url}")
        except Exception as exc:
            return PublishResponse(
                success=False,
                message=f"Thumbnail upload failed: {exc}",
                data={"video_id": video_id, "title": title, "thumbnail_uploaded": False},
            )

    return PublishResponse(
        success=True,
        message="Published to YouTube successfully.",
        data={
            "video_id": video_id,
            "title": title,
            "description": description,
            "tags": tags_list,
            "visibility": visibility,
            "thumbnail_uploaded": thumbnail_url is not None,
            "thumbnail_url": thumbnail_url,
            "youtube_video_id": update_response.get("id"),
        },
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "youtube-publisher"})
