"""YouTube Publisher - isolated sandbox for Phase 2."""

from __future__ import annotations

import os
import json
import pathlib
from typing import Optional

from fastapi import FastAPI, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

# Google imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io


app = FastAPI(title="YouTube Publisher", version="0.1.0")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
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
    return AuthStatusResponse(authorized=False, message="Not connected. Click Connect to authorize.")


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
            thumbnail_bytes = await thumbnail.read()
            thumbnail_body = MediaIoBaseUpload(
                io.BytesIO(thumbnail_bytes),
                mimetype=thumbnail.content_type or "image/png",
                resumable=True,
            )
            thumb_response = youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumbnail_body,
            ).execute()
            thumbnail_url = thumb_response.get("default", {}).get("url")
        except Exception as exc:
            return PublishResponse(
                success=True,
                message=f"Video metadata updated, but thumbnail upload failed: {exc}",
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
