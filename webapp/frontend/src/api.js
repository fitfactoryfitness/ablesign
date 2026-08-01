const BASE = 'http://127.0.0.1:8000'

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // ignore, keep statusText
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then(handle),
  screens: () => fetch(`${BASE}/api/screens`).then(handle),
  driveMonths: () => fetch(`${BASE}/api/drive/months`).then(handle),

  getSchedule: () => fetch(`${BASE}/api/schedule`).then(handle),
  saveSchedule: (rows) =>
    fetch(`${BASE}/api/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows }),
    }).then(handle),

  playlists: (screenIds) =>
    fetch(`${BASE}/api/playlist?screen_ids=${screenIds.join(',')}`).then(handle),
  playlistNow: (screenId) => fetch(`${BASE}/api/playlist/${screenId}/now`).then(handle),
  deletePlaylist: (screenId) =>
    fetch(`${BASE}/api/playlist/${screenId}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirmed: true }),
    }).then(handle),

  startUpload: (month, dryRun) =>
    fetch(`${BASE}/api/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month, dry_run: dryRun }),
    }).then(handle),

  createPlaylistPreview: (folder) =>
    fetch(`${BASE}/api/playlist/create/preview?folder=${encodeURIComponent(folder)}`).then(handle),
  createPlaylistExecute: (folder) =>
    fetch(`${BASE}/api/playlist/create/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder }),
    }).then(handle),

  jobStatus: (jobId) => fetch(`${BASE}/api/jobs/${jobId}`).then(handle),
}
