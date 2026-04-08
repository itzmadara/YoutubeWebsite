from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "jobs"
DOWNLOADS_DIR = BASE_DIR / "downloads"
TMP_DIR = BASE_DIR / "tmp"
LOCAL_COOKIES_FILE = BASE_DIR / "backend" / "cookies.txt"

SEGMENT_PRESETS = {
    "10s": 10,
    "30s": 30,
    "5min": 300,
}

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}

DEFAULT_ALLOWED_ORIGINS = {
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}

job_lock = threading.Lock()
jobs: dict[str, dict[str, Any]] = {}


def ensure_directories() -> None:
    for directory in (JOBS_DIR, DOWNLOADS_DIR, TMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def check_dependency(command_name: str) -> bool:
    return shutil.which(command_name) is not None


def is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.netloc.lower()
    if host not in YOUTUBE_HOSTS:
        return False

    if host.endswith("youtu.be"):
        return bool(parsed.path.strip("/"))

    query = parse_qs(parsed.query)
    return "v" in query or parsed.path.startswith("/shorts/")


def get_allowed_origins() -> set[str]:
    configured = os.environ.get("FRONTEND_ORIGIN", "").strip()
    if not configured:
        return set(DEFAULT_ALLOWED_ORIGINS)
    return {origin.strip() for origin in configured.split(",") if origin.strip()}


def get_download_base_url() -> str:
    app_url = os.environ.get("APP_BASE_URL", "").strip()
    if app_url:
        return app_url.rstrip("/")
    return ""


def get_yt_dlp_user_agent() -> str:
    return os.environ.get("YTDLP_USER_AGENT", "").strip()


def get_yt_dlp_js_runtimes() -> str:
    return os.environ.get("YTDLP_JS_RUNTIMES", "deno").strip()


def get_yt_dlp_remote_components() -> str:
    return os.environ.get("YTDLP_REMOTE_COMPONENTS", "ejs:github").strip()


def resolve_cookies_file() -> str | None:
    cookies_b64 = os.environ.get("YTDLP_COOKIES_B64", "").strip()
    if cookies_b64:
        cookie_path = TMP_DIR / "yt-dlp-cookies.txt"
        cookie_path.write_text(base64.b64decode(cookies_b64).decode("utf-8"), encoding="utf-8")
        return str(cookie_path)

    cookies_content = os.environ.get("YTDLP_COOKIES_CONTENT", "")
    if cookies_content.strip():
        cookie_path = TMP_DIR / "yt-dlp-cookies.txt"
        cookie_path.write_text(cookies_content, encoding="utf-8")
        return str(cookie_path)

    configured_file = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if configured_file and Path(configured_file).is_file():
        return configured_file

    if LOCAL_COOKIES_FILE.is_file():
        return str(LOCAL_COOKIES_FILE)

    return None


def get_yt_dlp_auth_args() -> list[str]:
    command_args: list[str] = []
    js_runtimes = get_yt_dlp_js_runtimes()
    if js_runtimes:
        command_args.extend(["--js-runtimes", js_runtimes])

    remote_components = get_yt_dlp_remote_components()
    if remote_components:
        command_args.extend(["--remote-components", remote_components])

    cookies_file = resolve_cookies_file()
    if cookies_file:
        command_args.extend(["--cookies", cookies_file])

    user_agent = get_yt_dlp_user_agent()
    if user_agent:
        command_args.extend(["--user-agent", user_agent])

    return command_args


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def update_job(job_id: str, **changes: Any) -> None:
    with job_lock:
        job = jobs[job_id]
        job.update(changes)
        job["updatedAt"] = int(time.time())


def list_output_files(job_output_dir: Path) -> list[dict[str, Any]]:
    files = []
    for path in sorted(job_output_dir.glob("*.mp4")):
        files.append(
            {
                "name": path.name,
                "sizeBytes": path.stat().st_size,
            }
        )
    return files


def download_video(job_id: str, youtube_url: str, temp_dir: Path) -> tuple[bool, str]:
    output_template = str(temp_dir / "source.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "bv*+ba/b",
        "-o",
        output_template,
        *get_yt_dlp_auth_args(),
        youtube_url,
    ]
    result = run_command(command)
    if result.returncode != 0:
        return False, result.stderr.strip() or "yt-dlp failed to download the video."

    candidates = sorted(temp_dir.glob("source.*"))
    if not candidates:
        return False, "Video was downloaded, but the file was not found."

    update_job(job_id, sourceFileName=candidates[0].name)
    return True, str(candidates[0])


def fetch_video_title(youtube_url: str) -> str:
    result = run_command(
        [
            "yt-dlp",
            "--dump-single-json",
            "--skip-download",
            "--no-playlist",
            *get_yt_dlp_auth_args(),
            youtube_url,
        ]
    )
    if result.returncode != 0:
        return "Untitled Video"

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "Untitled Video"

    title = str(payload.get("title") or "").strip()
    if not title:
        return "Untitled Video"
    return re.sub(r"[^\w\s-]", "", title)[:80].strip() or "Untitled Video"


def split_video(input_file: str, output_dir: Path, segment_seconds: int) -> tuple[bool, str]:
    pattern = str(output_dir / "clip_%03d.mp4")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        input_file,
        "-c",
        "copy",
        "-map",
        "0",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        pattern,
    ]
    result = run_command(command)
    if result.returncode != 0:
        return False, result.stderr.strip() or "ffmpeg could not split the video."

    if not list(output_dir.glob("*.mp4")):
        return False, "No output clips were created."
    return True, ""


def create_archive(job_id: str, title: str, segment_key: str, output_dir: Path) -> str:
    safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-").lower()
    base_name = f"{safe_title or 'youtube-clips'}-{segment_key}"
    zip_root = DOWNLOADS_DIR / f"{base_name}-{job_id}"
    archive_path = shutil.make_archive(str(zip_root), "zip", root_dir=output_dir)
    return Path(archive_path).name


def build_download_url(job_id: str) -> str:
    base_url = get_download_base_url()
    path = f"/api/jobs/{job_id}/download"
    return f"{base_url}{path}" if base_url else path


def process_job(job_id: str) -> None:
    with job_lock:
        job = dict(jobs[job_id])

    youtube_url = job["youtubeUrl"]
    segment_key = job["segmentPreset"]
    segment_seconds = SEGMENT_PRESETS[segment_key]
    job_temp_dir = TMP_DIR / job_id
    job_output_dir = JOBS_DIR / job_id
    job_temp_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        update_job(job_id, status="running", step="Checking dependencies")

        if not check_dependency("yt-dlp"):
            update_job(
                job_id,
                status="failed",
                step="Missing dependency",
                error="yt-dlp is required but was not found on this machine.",
            )
            return

        if not check_dependency("ffmpeg"):
            update_job(
                job_id,
                status="failed",
                step="Missing dependency",
                error="ffmpeg is required to cut the video into clips. Install ffmpeg, then try again.",
            )
            return

        title = fetch_video_title(youtube_url)
        update_job(job_id, title=title, step="Downloading video")
        downloaded, download_result = download_video(job_id, youtube_url, job_temp_dir)
        if not downloaded:
            update_job(job_id, status="failed", step="Download failed", error=download_result)
            return

        update_job(job_id, step="Creating clips")
        split_ok, split_error = split_video(download_result, job_output_dir, segment_seconds)
        if not split_ok:
            update_job(job_id, status="failed", step="Split failed", error=split_error)
            return

        update_job(job_id, step="Packaging clips")
        archive_name = create_archive(job_id, title, segment_key, job_output_dir)
        output_files = list_output_files(job_output_dir)

        update_job(
            job_id,
            status="completed",
            step="Finished",
            archiveName=archive_name,
            archiveUrl=build_download_url(job_id),
            clipCount=len(output_files),
            clips=output_files,
        )
    except Exception as exc:  # noqa: BLE001
        update_job(job_id, status="failed", step="Unexpected error", error=str(exc))


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ClipForgeAPI/1.0"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_json(
                {
                    "ok": True,
                    "message": "ClipForge backend is running.",
                    "docs": {
                        "system": "/api/system",
                        "createJob": "/api/jobs",
                        "jobStatus": "/api/jobs/<job_id>",
                        "download": "/api/jobs/<job_id>/download",
                    },
                }
            )
            return

        if parsed.path == "/api/system":
            self.send_json(
                {
                    "ok": True,
                    "dependencies": {
                        "ytDlp": check_dependency("yt-dlp"),
                        "ffmpeg": check_dependency("ffmpeg"),
                    },
                    "youtubeAuth": {
                        "cookiesConfigured": resolve_cookies_file() is not None,
                        "userAgentConfigured": bool(get_yt_dlp_user_agent()),
                        "jsRuntimes": get_yt_dlp_js_runtimes(),
                        "remoteComponents": get_yt_dlp_remote_components(),
                    },
                    "presets": [
                        {"key": key, "seconds": value}
                        for key, value in SEGMENT_PRESETS.items()
                    ],
                    "cors": {
                        "frontendOrigins": sorted(get_allowed_origins()),
                    },
                }
            )
            return

        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/download"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 4:
                self.handle_download(parts[2])
                return

        if parsed.path.startswith("/api/jobs/"):
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 3:
                self.handle_job_status(parts[2])
                return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/jobs":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self.send_json({"ok": False, "error": "Request body must be valid JSON."}, status=400)
            return

        youtube_url = str(payload.get("youtubeUrl") or "").strip()
        segment_preset = str(payload.get("segmentPreset") or "").strip()

        if not is_youtube_url(youtube_url):
            self.send_json({"ok": False, "error": "Please enter a valid YouTube video link."}, status=400)
            return

        if segment_preset not in SEGMENT_PRESETS:
            self.send_json({"ok": False, "error": "Please choose a supported clip duration."}, status=400)
            return

        job_id = uuid.uuid4().hex[:12]
        job_payload = {
            "id": job_id,
            "youtubeUrl": youtube_url,
            "segmentPreset": segment_preset,
            "segmentSeconds": SEGMENT_PRESETS[segment_preset],
            "status": "queued",
            "step": "Queued",
            "title": "Preparing job",
            "clipCount": 0,
            "clips": [],
            "archiveName": None,
            "archiveUrl": None,
            "error": None,
            "sourceFileName": None,
            "createdAt": int(time.time()),
            "updatedAt": int(time.time()),
        }

        with job_lock:
            jobs[job_id] = job_payload

        worker = threading.Thread(target=process_job, args=(job_id,), daemon=True)
        worker.start()

        self.send_json({"ok": True, "job": job_payload}, status=201)

    def end_headers(self) -> None:
        origin = self.headers.get("Origin")
        allowed_origins = get_allowed_origins()
        if origin and origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        elif not origin:
            self.send_header("Access-Control-Allow-Origin", "*")

        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def handle_job_status(self, job_id: str) -> None:
        with job_lock:
            job = jobs.get(job_id)

        if not job:
            self.send_json({"ok": False, "error": "Job not found."}, status=404)
            return

        self.send_json({"ok": True, "job": job})

    def handle_download(self, job_id: str) -> None:
        with job_lock:
            job = jobs.get(job_id)

        if not job or not job.get("archiveName"):
            self.send_json({"ok": False, "error": "Download is not ready yet."}, status=404)
            return

        archive_path = DOWNLOADS_DIR / job["archiveName"]
        if not archive_path.exists():
            self.send_json({"ok": False, "error": "Archive file is missing."}, status=404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(archive_path.stat().st_size))
        self.send_header("Content-Disposition", f'attachment; filename="{archive_path.name}"')
        self.end_headers()
        with archive_path.open("rb") as archive_file:
            shutil.copyfileobj(archive_file, self.wfile)

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format_string: str, *args: Any) -> None:
        return


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    ensure_directories()
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"ClipForge backend running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")))
