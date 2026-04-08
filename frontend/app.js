const API_BASE_URL = (window.CLIPFORGE_API_BASE_URL || "").replace(/\/$/, "");
const isPlaceholderApi =
  !API_BASE_URL || API_BASE_URL.includes("your-heroku-app.herokuapp.com");

const form = document.getElementById("clip-form");
const submitButton = document.getElementById("submit-button");
const systemStatus = document.getElementById("system-status");
const apiTarget = document.getElementById("api-target");
const jobState = document.getElementById("job-state");
const clipResults = document.getElementById("clip-results");
const videoTitle = document.getElementById("video-title");
const clipCount = document.getElementById("clip-count");
const clipList = document.getElementById("clip-list");
const downloadLink = document.getElementById("download-link");

let pollTimer = null;

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

function formatBytes(bytes) {
  if (!bytes) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let index = 0;

  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function setSystemStatus(message, variant) {
  systemStatus.textContent = message;
  systemStatus.className = `system-status ${variant}`;
}

function setApiTargetStatus() {
  if (isPlaceholderApi) {
    apiTarget.textContent = "Set your Heroku backend URL in frontend/config.js before deploying to Vercel.";
    apiTarget.className = "system-status warning";
    return;
  }

  apiTarget.textContent = `Frontend is connected to ${API_BASE_URL}`;
  apiTarget.className = "system-status success";
}

async function loadSystemStatus() {
  if (isPlaceholderApi) {
    setSystemStatus("Backend URL is still a placeholder, so API checks are paused.", "warning");
    return;
  }

  try {
    const response = await fetch(apiUrl("/api/system"));
    const payload = await response.json();

    if (payload.dependencies.ytDlp && payload.dependencies.ffmpeg) {
      setSystemStatus("yt-dlp and ffmpeg are installed. The backend is ready to create clips.", "success");
      return;
    }

    const missing = [];
    if (!payload.dependencies.ytDlp) {
      missing.push("yt-dlp");
    }
    if (!payload.dependencies.ffmpeg) {
      missing.push("ffmpeg");
    }

    setSystemStatus(
      `Missing dependency: ${missing.join(", ")}. Install it on Heroku before running real clip jobs.`,
      "warning"
    );
  } catch (error) {
    setSystemStatus("Could not reach the backend. Check the Heroku URL and CORS settings.", "warning");
  }
}

function renderJobState(job) {
  jobState.className = `job-state ${job.status}`;

  if (job.status === "queued") {
    jobState.textContent = `Job queued. Preparing ${job.segmentPreset} clips...`;
  } else if (job.status === "running") {
    jobState.textContent = `${job.step}... this can take a little time for long videos.`;
  } else if (job.status === "failed") {
    jobState.textContent = `${job.step}: ${job.error || "Something went wrong."}`;
  } else if (job.status === "completed") {
    jobState.textContent = `Finished. ${job.clipCount} clips are ready for download.`;
  }
}

function renderResults(job) {
  clipResults.classList.remove("hidden");
  videoTitle.textContent = job.title || "Untitled Video";
  clipCount.textContent = job.clipCount || 0;

  clipList.innerHTML = "";
  for (const clip of job.clips || []) {
    const item = document.createElement("div");
    item.className = "clip-list-item";

    const name = document.createElement("div");
    name.className = "clip-name";
    name.textContent = clip.name;

    const size = document.createElement("div");
    size.className = "clip-size";
    size.textContent = formatBytes(clip.sizeBytes);

    item.append(name, size);
    clipList.appendChild(item);
  }

  if (job.status === "completed" && job.archiveUrl) {
    downloadLink.href = job.archiveUrl.startsWith("http")
      ? job.archiveUrl
      : apiUrl(job.archiveUrl);
    downloadLink.classList.remove("hidden");
  } else {
    downloadLink.classList.add("hidden");
  }
}

function stopPolling() {
  if (pollTimer) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
  }
}

async function pollJob(jobId) {
  try {
    const response = await fetch(apiUrl(`/api/jobs/${jobId}`));
    const payload = await response.json();

    if (!payload.ok) {
      throw new Error(payload.error || "Could not read job status.");
    }

    const job = payload.job;
    renderJobState(job);
    renderResults(job);

    if (job.status === "queued" || job.status === "running") {
      pollTimer = window.setTimeout(() => pollJob(jobId), 2500);
      return;
    }

    submitButton.disabled = false;
    submitButton.textContent = "Start clipping";
  } catch (error) {
    stopPolling();
    submitButton.disabled = false;
    submitButton.textContent = "Start clipping";
    jobState.className = "job-state failed";
    jobState.textContent = error.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (isPlaceholderApi) {
    jobState.className = "job-state failed";
    jobState.textContent = "Set the real Heroku backend URL in frontend/config.js before creating jobs.";
    return;
  }

  stopPolling();
  submitButton.disabled = true;
  submitButton.textContent = "Creating job...";
  jobState.className = "job-state running";
  jobState.textContent = "Submitting job to backend...";
  clipResults.classList.add("hidden");
  downloadLink.classList.add("hidden");

  const formData = new FormData(form);
  const payload = {
    youtubeUrl: formData.get("youtubeUrl"),
    segmentPreset: formData.get("segmentPreset"),
  };

  try {
    const response = await fetch(apiUrl("/api/jobs"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || "Could not create job.");
    }

    renderJobState(result.job);
    renderResults(result.job);
    submitButton.textContent = "Processing...";
    pollJob(result.job.id);
  } catch (error) {
    submitButton.disabled = false;
    submitButton.textContent = "Start clipping";
    jobState.className = "job-state failed";
    jobState.textContent = error.message;
  }
});

setApiTargetStatus();
loadSystemStatus();
