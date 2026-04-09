# ClipForge

ClipForge is now split for deployment:

- `frontend/` is a static site you can deploy to Vercel
- `backend/` is a Python API you can deploy to your VPS

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
- `deploy/clipforge.service`: `systemd` service for a VPS backend
- `deploy/clipforge.env.example`: backend environment variables for a VPS
- `deploy/nginx-clipforge.conf`: nginx reverse proxy example for a VPS
- `deploy/vps-setup.sh`: starter script for installing VPS dependencies
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
2. In [frontend/config.js](/Users/vikashkumar/YoutubeWebsite/frontend/config.js), replace the placeholder backend URL with your real VPS backend URL like `https://api.yourdomain.com`.
3. Deploy.

This repo now also includes a root-level [vercel.json](/Users/vikashkumar/YoutubeWebsite/vercel.json) that explicitly deploys only the static files from `frontend/`. This avoids Vercel trying to treat the repo as a Python app because of the separate `backend/` folder.

## Deploy backend to a VPS

Recommended stack:

- Ubuntu VPS
- Python 3 virtualenv
- `ffmpeg`
- Node 22
- nginx
- `systemd`

Files provided:

- [deploy/clipforge.service](/Users/vikashkumar/YoutubeWebsite/deploy/clipforge.service)
- [deploy/clipforge.env.example](/Users/vikashkumar/YoutubeWebsite/deploy/clipforge.env.example)
- [deploy/nginx-clipforge.conf](/Users/vikashkumar/YoutubeWebsite/deploy/nginx-clipforge.conf)
- [deploy/vps-setup.sh](/Users/vikashkumar/YoutubeWebsite/deploy/vps-setup.sh)

Typical VPS layout:

```text
/opt/clipforge/app
/opt/clipforge/venv
/opt/clipforge/secrets/cookies.txt
```

Typical VPS steps:

1. Clone this repo to `/opt/clipforge/app`
2. Run [deploy/vps-setup.sh](/Users/vikashkumar/YoutubeWebsite/deploy/vps-setup.sh)
3. Copy [deploy/clipforge.env.example](/Users/vikashkumar/YoutubeWebsite/deploy/clipforge.env.example) to `deploy/clipforge.env`
4. Edit `deploy/clipforge.env` with your real domain and frontend URL
5. Put your private cookies file at `/opt/clipforge/secrets/cookies.txt`
6. Copy [deploy/clipforge.service](/Users/vikashkumar/YoutubeWebsite/deploy/clipforge.service) to `/etc/systemd/system/clipforge.service`
7. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clipforge
sudo systemctl start clipforge
sudo systemctl status clipforge
```

8. Copy [deploy/nginx-clipforge.conf](/Users/vikashkumar/YoutubeWebsite/deploy/nginx-clipforge.conf) to `/etc/nginx/sites-available/clipforge`
9. Enable nginx site and reload:

```bash
sudo ln -s /etc/nginx/sites-available/clipforge /etc/nginx/sites-enabled/clipforge
sudo nginx -t
sudo systemctl reload nginx
```

10. Point your domain, for example `api.yourdomain.com`, to the VPS and add HTTPS with Let's Encrypt.

## Heroku note

1. Create a Heroku app from this repo.
2. This repo now includes both [Procfile](/Users/vikashkumar/YoutubeWebsite/Procfile) for buildpack-style deploys and [heroku.yml](/Users/vikashkumar/YoutubeWebsite/heroku.yml) with [Dockerfile](/Users/vikashkumar/YoutubeWebsite/Dockerfile) for container deploys.
3. Set config vars:

```text
FRONTEND_ORIGIN=https://your-vercel-project.vercel.app
APP_BASE_URL=https://your-heroku-app.herokuapp.com
```

4. Make sure `ffmpeg` is installed in the Heroku environment, otherwise clip jobs will fail with a clear dependency error.

If your Heroku app is already configured for container deploys, the included `heroku.yml` fixes the "does not include a heroku.yml build manifest" error and installs `ffmpeg` inside the container image.

## YouTube cookies

If YouTube asks to "Sign in to confirm you're not a bot", add cookies on the backend side, not on Vercel.

Options:

- Local development: put your exported Netscape-format cookies file at `backend/cookies.txt`
- Heroku: set one of these config vars on the backend app

```text
YTDLP_COOKIES_B64=...
YTDLP_COOKIES_CONTENT=...
YTDLP_COOKIES_FILE=/absolute/path/to/cookies.txt
YTDLP_USER_AGENT=your-browser-user-agent
```

Recommended for Heroku:

1. Export your `cookies.txt` file from the browser.
2. Base64 encode it.
3. Put that value into `YTDLP_COOKIES_B64` in Heroku config vars.
4. Optionally set `YTDLP_USER_AGENT` to your browser's user agent.
5. Redeploy Heroku so the backend picks up the updated container image and config vars.

## YouTube JS challenge runtime

Recent yt-dlp YouTube extraction can also require a JavaScript runtime and EJS challenge components.

This repo now defaults to:

```text
YTDLP_JS_RUNTIMES=node
YTDLP_REMOTE_COMPONENTS=ejs:github
```

The Heroku Docker image now installs Node 22, and `yt-dlp[default]` is used so the backend is better aligned with current yt-dlp YouTube requirements.

Important:

- Do not put cookies in the frontend.
- Do not commit `backend/cookies.txt` to GitHub.
- Browser cookies from your local machine may still be unreliable on Heroku because the requests come from a different server IP than your browser session.
- On a VPS, prefer `YTDLP_COOKIES_FILE=/opt/clipforge/secrets/cookies.txt` instead of storing cookies in app config vars.

## Important hosting note

This version is much better on a VPS than on Heroku, but it still uses in-memory jobs and local file storage. For production at larger scale, move job state to Redis or a database and store clips in S3 or another object store.

## Run tests

```bash
python3 -m unittest discover -s tests
```

## Important note

This app should only be used for videos you own or are authorized to process. YouTube content may be protected by platform rules, copyright law, or both.
