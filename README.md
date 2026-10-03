<p align="center">
  <img src="https://img.shields.io/badge/YouTube_SEO_Studio-Full--Stack-blue?style=for-the-badge" alt="YouTube SEO Studio"/>
  <br/>
  <strong>AI-powered YouTube SEO generation + one-click YouTube publishing.</strong>
  <br/>
  Built with FastAPI · React · Gemini AI · Docker
</p>

---

## Table of Contents

### For Developers & Technical Users

- [What Problem Does This Solve?](#what-problem-does-this-solve)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
  - [Backend Architecture](#backend-architecture)
  - [Frontend Architecture](#frontend-architecture)
  - [Database](#database)
  - [Authentication Flow (Phase 2)](#authentication-flow-phase-2)
- [Project Phases](#project-phases)
  - [Phase 1 — SEO Content Generation](#phase-1--seo-content-generation)
  - [Phase 2 — YouTube Publishing](#phase-2--youtube-publishing)
- [Running in Development](#running-in-development)
- [Configuration](#configuration)

### For Non-Technical Users

- [What Problem Does This Solve?](#what-problem-does-this-solve-1)
- [Key Features](#key-features-1)
- [Prerequisites](#prerequisites)
- [Step-by-Step Setup](#step-by-step-setup)
- [How to Use the App](#how-to-use-the-app)
- [Troubleshooting for Non-Technical Users](#troubleshooting-for-non-technical-users)

### Community

- [Star This Repo](#star-this-repo)
- [Contributing](#contributing)
- [Managing This Open Source Project](#managing-this-open-source-project)

---

## What Problem Does This Solve?

Creating and optimizing YouTube content is time-consuming. Creators struggle with:

- Writing titles, descriptions, and tags that rank well in search.
- Understanding which topics resonate most with their audience.
- Manually uploading optimized metadata to YouTube after creating content.

**YouTube SEO Studio** automates the SEO research part and bridges the gap between content creation and publishing — all in one place.

---

## Key Features

| Feature                       | Description                                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **AI-Powered SEO Generation** | Upload any video and get an optimized title, description, tags, and topic timeline powered by Google Gemini.           |
| **YouTube Integration**       | Connect your YouTube channel once, then publish directly from the app — no copy-pasting metadata manually.             |
| **Smart Defaults**            | Default visibility is set to **Private** so you never accidentally publish unfinished content.                         |
| **Dark & Light Theme**        | Full dark/light mode support that works everywhere in the app.                                                         |
| **Local-First** | Your video never leaves your machine. For SEO analysis, only the extracted audio is sent to Google Gemini — never the full video file. A fully offline/local version is planned for a future release. |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌────────────┐     ┌────────────┐     ┌──────────────────────┐ │
│  │ PostgreSQL │     │  Backend   │     │      Frontend        │ │
│  │  (Port     │────▶│  (Port     │────▶│   (Port 8080)        │ │
│  │   5432)    │     │   8000)    │     │   Nginx + React      │ │
│  └────────────┘     └────────────┘     └──────────────────────┘ │
│        ▲                  │                                      │
│        │                  │  FFmpeg + Gemini + YouTube API       │
│        │                  │                                      │
│        └──────────────────┘                                      │
│                  Persistent worker loop                          │
└─────────────────────────────────────────────────────────────────┘
```

### Backend Architecture

The backend is a **FastAPI** application (Python 3.12) with an in-process persistent worker — no separate worker container, no Redis, no Celery.

| Layer            | Technology          | Purpose                                                                 |
| ---------------- | ------------------- | ----------------------------------------------------------------------- |
| **API Router**   | FastAPI `APIRouter` | Versioned REST endpoints under `/api/v1`                                |
| **Services**     | Python async        | Business logic: Gemini AI calls, FFmpeg processing, YouTube Data API v3 |
| **Repositories** | SQLAlchemy async    | Data access layer (clean separation from models)                        |
| **Models**       | SQLAlchemy ORM      | Database schema definitions                                             |
| **Schemas**      | Pydantic v2         | Request validation and response serialization                           |
| **Worker**       | In-process loop     | Polls for pending jobs, processes them, updates status                  |
| **Migrations**   | Alembic             | Database schema versioning                                              |

**Key backend responsibilities:**

- Accept video file uploads of any length (including 10+ hour videos) via resumable multipart upload
- Extract audio via FFmpeg and chunk it for AI processing
- Send only the extracted audio chunks to Google Gemini — the original video never leaves your machine
- Store results in PostgreSQL
- Handle YouTube OAuth flow and publish videos via YouTube Data API v3

### Frontend Architecture

The frontend is a **React 18** single-page application built with **Vite 6** and styled with **Tailwind CSS**.

| Layer           | Technology     | Purpose                                                               |
| --------------- | -------------- | --------------------------------------------------------------------- |
| **Pages**       | React Router   | Route-level pages: job creation, job detail, publish, video selection |
| **Components**  | Reusable JSX   | UI primitives + feature-specific components                           |
| **State**       | Zustand        | Theme (dark/light), UI state, toast notifications                     |
| **API Clients** | Fetch + Axios  | Type-safe API calls to backend                                        |
| **Styling**     | Tailwind CSS   | CSS-variable-driven color system with class-based dark mode           |
| **Build**       | Vite 6 + Nginx | Dev server with API proxy; production multi-stage Docker build        |

**In development**, Vite proxies `/api` and `/youtube` to the backend. **In production (Docker)**, Nginx serves the built SPA and proxies `/api/` to the backend.

### Database

- **Engine:** PostgreSQL 16 (Alpine)
- **Driver:** asyncpg (async SQLAlchemy)
- **Migrations:** Alembic (auto-run on container startup)
- **Persistence:** Docker volume `postgres_data`
- **Default credentials:** `postgres` / `postgres` (change in `.env`)

### Authentication Flow (Phase 2)

```
┌──────────┐        ┌──────────┐        ┌──────────────────┐
│ Browser  │───────▶│ Frontend │───────▶│   Backend        │
│          │ click  │          │ fetch  │                  │
│          │ Connect│          │ auth   │  Generate state  │
│          │ YouTube │          │   URL  │  + auth URL      │
└──────────┘        └──────────┘        └────────┬─────────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │ Google OAuth   │
                                         │ Consent Screen │
                                         └───────┬────────┘
                                                 │ user consents
                                                 ▼
                                         ┌────────────────┐
                                         │ Backend        │
                                         │ /youtube/auth/ │
                                         │ callback       │
                                         │ - Validates    │
                                         │   state        │
                                         │ - Exchanges    │
                                         │   code for     │
                                         │   tokens       │
                                         │ - Saves to     │
                                         │   data/        │
                                         │   youtube-     │
                                         │   tokens/      │
                                         │ - Redirects    │
                                         │   to frontend  │
                                         └───────┬────────┘
                                                 │
                                                 ▼
                                         ┌────────────────┐
                                         │ Frontend       │
                                         │ Shows "Connected"│
                                         └────────────────┘
```

---

## Project Phases

### Phase 1 — SEO Content Generation

The core of the application. No external accounts needed. The entire system is built around the **Google Gemini free tier** — you can generate unlimited SEO metadata at no cost using a free API key.

> **Note:** A fully offline/local version (running AI entirely on your machine) is planned for a future release for users who want 100% privacy.

1. **Upload** — Pick a local video file from your computer. The app supports all common video formats and handles large files (even 10+ hours) via resumable upload.
2. **Processing** — The backend uses FFmpeg to extract audio, splits it into chunks, and sends it to Google Gemini.
3. **AI Analysis** — Gemini returns:
   - Optimized title (max 100 characters)
   - Description (max 5000 characters)
   - Comma-separated tags
   - Topic timeline breakdown
4. **Review** — View and copy the SEO output from the Job Detail page.
5. **Local Storage** — SEO data is saved in the browser's localStorage for convenience.

### Phase 2 — YouTube Publishing

Requires a Google Cloud account and OAuth setup.

1. **Connect YouTube** — One-click OAuth 2.0 flow via Google.
2. **Select Video** — Browse your channel videos and playlists, or enter a video ID manually.
3. **Compose** — Title, description, and tags are pre-filled from the SEO output. Upload a custom thumbnail (auto-compressed client-side).
4. **Choose Visibility** — Public, Unlisted, or Private (default: **Private** to prevent accidental uploads).
5. **Publish** — One-click publish to YouTube via YouTube Data API v3.

---

## Running in Development

### Prerequisites

| Tool                     | Version                            | Why                                                  |
| ------------------------ | ---------------------------------- | ---------------------------------------------------- |
| **Docker Desktop**       | Latest stable                      | Runs PostgreSQL, backend, and frontend in containers |
| **Docker Compose**       | v2+ (included with Docker Desktop) | Orchestrates the 3 services                          |
| **Node.js**              | ≥ 18                               | Frontend development (`npm install`, `npm run dev`)  |
| **Python**               | ≥ 3.12                             | Backend development (`pip install`, `uvicorn`)       |
| **Git**                  | Any                                | Clone the repository                                 |
| **Google Cloud account** | Free tier is fine                  | Gemini API key and YouTube OAuth (Phase 2)           |

### Project Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd youtube-seo-studio

# 2. Create environment file
cp .env.example .env

# 3. Edit .env and add your GEMINI_API_KEY
#    (Get one free at https://aistudio.google.com/app/apikey)

# 4. Start the stack
docker compose down   # optional — clean slate
docker compose up -d --build

# 5. Verify
docker compose ps
curl http://127.0.0.1:8000/api/v1/health
```

### Useful Commands

```bash
# View logs
docker compose logs -f          # all services
docker compose logs -f backend  # backend only

# Stop (keeps data)
docker compose stop

# Stop and remove containers (keeps volumes)
docker compose down

# Stop, remove containers AND volumes (deletes database)
docker compose down -v

# Restart after code changes
docker compose up -d --build
```

### Configuration

All configuration is via environment variables in `.env`. Key variables:

| Variable               | Purpose                                      |
| ---------------------- | -------------------------------------------- |
| `GEMINI_API_KEY`       | Google Gemini API key (required for Phase 1) |
| `AI_PROVIDER`          | `gemini` (real) or `mock` (offline testing)  |
| `POSTGRES_DB`          | Database name                                |
| `POSTGRES_USER`        | Database username                            |
| `POSTGRES_PASSWORD`    | Database password                            |
| `YOUTUBE_REDIRECT_URI` | OAuth callback URL (Phase 2)                 |
| `YOUTUBE_FRONTEND_URL` | Where to redirect after OAuth (Phase 2)      |

See `.env.example` for the full list of available options.

---

## What Problem Does This Solve?

Creating and optimizing YouTube content is time-consuming. Creators struggle with:

- Writing titles, descriptions, and tags that actually rank in search.
- Manually uploading optimized metadata to YouTube after creating content.
- Getting AI-powered insights without switching between 5 different tools.

**YouTube SEO Studio** solves this by combining AI-powered SEO generation with direct YouTube publishing in one application. You upload a video, get AI-generated SEO metadata, review it, and publish to YouTube — all without leaving the app.

---

## Key Features

| Feature                       | Description                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **AI-Powered SEO Generation** | Upload any video and get an optimized title, description, tags, and topic timeline powered by Google Gemini. |
| **YouTube Integration**       | Connect your YouTube channel once, then publish directly from the app.                                       |
| **Smart Defaults**            | Default visibility is set to **Private** so you never accidentally publish unfinished content.               |
| **Dark & Light Theme**        | Full dark/light mode support that works everywhere in the app.                                               |
| **Local-First**               | All data stays on your machine. No cloud accounts required for SEO generation.                               |

---

## Prerequisites

To run this application, you only need **one thing**:

### Download Docker Desktop

Docker is a tool that runs applications in isolated containers. It means you don't need to install Python, Node.js, PostgreSQL, or any other software manually. Everything is packaged and runs automatically.

| Platform                  | Download Link                                                                                      |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| **Windows / Mac / Linux** | [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) |

**After downloading:**

1. Install Docker Desktop like any normal program.
2. Open it and wait until it says "Docker is running" (you'll see a whale icon in your system tray).
3. That's it. You don't need to know anything else about Docker.

**Additional requirement (for YouTube publishing only):**

- A **Google Cloud account** (free tier is fine) — needed only if you want to use the YouTube publishing feature. SEO generation works without it.

---

## Step-by-Step Setup

### Step 1 — Install Git

If you don't have Git already:

- Download from [https://git-scm.com/downloads](https://git-scm.com/downloads)
- Install it like any normal program.

### Step 2 — Download the Project

Open a terminal (Command Prompt or PowerShell on Windows, Terminal on Mac/Linux) and run:

```bash
git clone https://github.com/<your-username>/youtube-seo-studio.git
cd youtube-seo-studio
```

> **Note for Windows users:** If you see a message saying "git is not recognized", close the terminal and reopen it after installing Git.

### Step 3 — Create Your Configuration File

```bash
# On Windows (PowerShell)
copy .env.example .env

# On Mac/Linux
cp .env.example .env
```

Now you need to open the `.env` file in a text editor (like Notepad) and add one thing:

Find this line:

```
GEMINI_API_KEY=your-api-key-here
```

Replace `your-api-key-here` with your actual API key.

**How to get a Gemini API key:**

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account.
3. Click **"Get API Key"** or **"Create API Key"**.
4. Copy the key and paste it in place of `your-api-key-here`.

Save the `.env` file and close it.

### Step 4 — Start the Application

In the terminal (make sure you're still inside the `youtube-seo-studio` folder), run:

```bash
docker compose up -d --build
```

This command does the following:

1. Downloads and builds the application containers (takes 2-5 minutes the first time).
2. Starts the PostgreSQL database.
3. Runs database migrations automatically.
4. Starts the backend server.
5. Starts the frontend application.

**Wait until the command finishes.** You should see your terminal prompt again.

### Step 5 — Verify It's Running

Run this command:

```bash
docker compose ps
```

You should see something like:

```
NAME                SERVICE   STATUS
yss-postgres        postgres  running
yss-backend         backend   running
yss-frontend        frontend  running
```

All three should say **running** or **healthy**. If they say "starting" or "unhealthy", wait a minute and run the command again.

### Step 6 — Open the Application

Open your web browser (Chrome, Firefox, Edge, etc.) and go to:

```
http://localhost:8080
```

You should see the YouTube SEO Studio application.

---

## How to Use the App

### Generating SEO Content (Phase 1)

1. Open `http://localhost:8080` in your browser.
2. Look for a **"New Job"** button or a **"+"** button and click it.
3. You can either:
   - **Upload a video file** from your computer.
4. Click **"Start Processing"**.
5. Wait. This can take a few minutes depending on the video length. You can see the status on the screen.
6. When it's done, you'll see the generated **title**, **description**, **tags**, and **timeline**.
7. You can click on any field to copy it.

### Publishing to YouTube (Phase 2)

If you want to publish directly to YouTube:

1. Make sure you have a **Google Cloud account** and have set up the YouTube API (see the Developer section above for details).
2. In the app, go to the **Publish** page of a completed job.
3. Click **"Connect YouTube"**.
4. A popup will open asking you to sign in to your Google account and grant permissions.
5. After you approve, the popup closes and you'll see **"YouTube API: Connected"**.
6. Select a video from your channel or enter a video ID.
7. Review the SEO metadata (title, description, tags).
8. Choose **visibility** (Public, Unlisted, or Private). Default is **Private** for safety.
9. Optionally upload a custom thumbnail.
10. Click **"Publish to YouTube"**.

---

## Troubleshooting for Non-Technical Users

### "The page won't load" or "localhost refused to connect"

1. Make sure Docker Desktop is running. Look for the whale icon in your system tray.
2. Open a terminal and run:
   ```bash
   docker compose ps
   ```
3. If you see any containers with status **"exited"** or **"unhealthy"**, run:
   ```bash
   docker compose up -d --build
   ```

### "It's taking forever to start"

The first time you run the app, Docker needs to download and build everything. This can take 5-10 minutes depending on your internet speed. After the first run, it will be much faster.

### "I see a blank white screen"

This usually means the frontend container is still starting. Wait 30 seconds and refresh the page. If it persists:

```bash
docker compose up -d --build
```

### "I get a rate limit error from Gemini"

The free Gemini API has usage limits. If you see an error about rate limits:

1. Wait 1-2 minutes.
2. Try again.
3. If it keeps happening, you may need to wait a few hours or upgrade your Google Cloud plan.

### "The YouTube connect button doesn't work"

1. Make sure you have created `client_secrets.json` in the project root folder.
2. Make sure the file contains the correct redirect URI.
3. Rebuild the backend container:
   ```bash
   docker compose up -d --build
   ```

### "I messed up and want to start fresh"

```bash
docker compose down -v
docker compose up -d --build
```

**Warning:** `down -v` deletes all data in the database. You'll lose all your SEO jobs.

### "How do I stop the app?"

```bash
docker compose stop
```

This keeps all your data. To start it again later:

```bash
docker compose up -d
```

### "How do I completely remove the app?"

```bash
docker compose down -v
```

This removes the containers and the database. Your project files (the code you downloaded) are still safe — only the data inside Docker is removed.

---

## Star This Repo

If you found this project useful, please consider giving it a star on GitHub. It helps others discover the project and motivates continued development.

---

## Contributing

Contributions are welcome! Whether it's a bug fix, feature request, documentation improvement, or design suggestion — all contributions are appreciated.

### How to Contribute

1. **Fork** the repository.
2. Create a **feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. Make your changes and **commit**:
   ```bash
   git commit -m "Add amazing feature"
   ```
4. **Push** to your branch:
   ```bash
   git push origin feature/amazing-feature
   ```
5. Open a **Pull Request** with a clear description of what you changed and why.

### Reporting Bugs

If you find a bug, please open an issue on GitHub with:

- A clear description of the bug.
- Steps to reproduce it.
- What you expected to happen.
- What actually happened.
- Screenshots if possible.

---

## Managing This Open Source Project

### A Note from the Creator

I built this project on my own, primarily for my own use, and I am sharing it openly in case it helps other creators too. I am the sole maintainer of this project.

I believe the best way to keep this project alive and useful is through community contributions. Whether you fix a typo, add a feature, or just share feedback — all of it helps. This project grows because people like you care enough to contribute.

### How This Project Works

| Area | What to Expect |
|------|---------------|
| **Issues** | Open an issue for bugs, questions, or ideas. I review and respond as I can. |
| **Pull Requests** | Small, focused changes are easiest to review and merge. I merge PRs when I have time to review them. |
| **Releases** | I push updates when meaningful changes are ready. There is no fixed schedule. |
| **Discussions** | Use GitHub Discussions for questions, ideas, or sharing how you use the project. |
| **Security** | Found a security issue? Please report it privately via GitHub Security Advisories. |

### How to Contribute

Contributions come in all shapes — you don't need to write code to make a difference.

- **Use the project** — the best feedback comes from real users. If something works well (or doesn't), let me know.
- **Report bugs** — open an issue with a clear description of what went wrong and how to reproduce it.
- **Improve documentation** — fix typos, clarify steps, add screenshots, or translate the README.
- **Share it** — if this project helped you, share it with other creators who might find it useful.
- **Fork and customize** — if you want to add features or change behavior, fork the repo and make it yours. You do not need my permission to use or modify the code.

### How to Submit a Pull Request

If you want to contribute code:

1. **Fork** the repository.
2. Create a **branch** for your change.
3. Keep changes **small and focused** — one fix or feature per PR is ideal.
4. Open the PR with a clear description of what you changed and why.

Small, well-scoped changes are much easier to review and merge quickly.

### Forking — Make It Yours

If this project is missing something for your workflow, or if you want to take it in a completely different direction — **fork it**. That is exactly what open source is for. You are free to:

- Use the code as a starting point for your own project.
- Add features that I do not have time to build.
- Change the architecture, AI provider, or anything else.
- Publish your own version.

I would love to hear about forks that go in interesting directions, but you are under no obligation to keep me in the loop.

I would love to hear about what you build, but you are under no obligation to keep me in the loop.

### License

This project is open source. Please add your preferred license (e.g., MIT, Apache 2.0) before publishing.
