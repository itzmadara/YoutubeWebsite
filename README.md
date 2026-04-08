# ClipForge

ClipForge is now split for trial hosting:

- `frontend/` is a static site you can deploy to Vercel
- `backend/` is a Python API you can deploy to Heroku

The app accepts a YouTube video URL and splits the full video into fixed clip sizes like `10s`, `30s`, or `5min`.

## What this version includes

- Single-page frontend with a strong landing section, clip duration picker, backend status, job polling, and ZIP download link
- Python backend API with a background worker
- YouTube URL validation
- `yt-dlp` download workflow
- `ffmpeg` clip splitting
- Automatic ZIP packaging for completed jobs
- Basic tests for URL validation and preset support

## Project structure

- `backend/app.py`: Python API and video processing backend
- `frontend/index.html`: frontend markup
- `frontend/styles.css`: visual design
- `frontend/app.js`: browser-side logic
- `frontend/config.js`: frontend API URL configuration
- `Procfile`: Heroku web command
- `requirements.txt`: Python dependencies for Heroku
- `tests/test_app.py`: basic test coverage

## Requirements

- Python 3.10+
- `yt-dlp`
- `ffmpeg`

`yt-dlp` is in `requirements.txt`. `ffmpeg` still needs to exist on the backend machine for real clip generation.

## Run backend locally

```bash
python3 backend/app.py
```

The backend runs on:

```text
http://127.0.0.1:8000
```

## Run frontend locally

Serve the `frontend/` folder with any static server. For example:

```bash
python3 -m http.server 3000 --directory frontend
```

Then open:

```text
http://127.0.0.1:3000
```

## Deploy frontend to Vercel

1. Import this repo into Vercel.
2. In [frontend/config.js](/Users/vikashkumar/YoutubeWebsite/frontend/config.js), replace `https://your-heroku-app.herokuapp.com` with your real Heroku backend URL.
3. Deploy.

This repo now also includes a root-level [vercel.json](/Users/vikashkumar/YoutubeWebsite/vercel.json) that explicitly deploys only the static files from `frontend/`. This avoids Vercel trying to treat the repo as a Python app because of the separate `backend/` folder.

## Deploy backend to Heroku

1. Create a Heroku app from this repo.
2. This repo now includes both [Procfile](/Users/vikashkumar/YoutubeWebsite/Procfile) for buildpack-style deploys and [heroku.yml](/Users/vikashkumar/YoutubeWebsite/heroku.yml) with [Dockerfile](/Users/vikashkumar/YoutubeWebsite/Dockerfile) for container deploys.
3. Set config vars:

```text
FRONTEND_ORIGIN=https://your-vercel-project.vercel.app
APP_BASE_URL=https://your-heroku-app.herokuapp.com
```

4. Make sure `ffmpeg` is installed in the Heroku environment, otherwise clip jobs will fail with a clear dependency error.

If your Heroku app is already configured for container deploys, the included `heroku.yml` fixes the "does not include a heroku.yml build manifest" error and installs `ffmpeg` inside the container image.

## Important trial note

This version is okay for trial hosting, but it still uses in-memory jobs and local file storage. On Heroku, jobs and ZIP files can disappear when the dyno restarts. For production, move job state to Redis or a database and store clips in S3 or another object store.

## Run tests

```bash
python3 -m unittest discover -s tests
```

## Important note

This app should only be used for videos you own or are authorized to process. YouTube content may be protected by platform rules, copyright law, or both.
