import React, { useEffect, useState } from 'react'
import { api } from '../api'
import Help from '../components/Help'
import ConfirmModal from '../components/ConfirmModal'
import JobLogPanel from '../components/JobLogPanel'

export default function CreatePlaylist() {
  const [months, setMonths] = useState(null)
  const [selectedMonth, setSelectedMonth] = useState('')
  const [preview, setPreview] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [jobId, setJobId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.driveMonths().then((list) => {
      setMonths(list)
      const aug = list.find((m) => m.name.toLowerCase().includes('august'))
      setSelectedMonth((aug || list[0])?.name || '')
    }).catch((e) => setError(e.message))
  }, [])

  const folder = selectedMonth ? `Claude/${selectedMonth}` : ''

  async function loadPreview() {
    if (!folder) return
    setLoadingPreview(true)
    setError(null)
    setPreview(null)
    try {
      const res = await api.createPlaylistPreview(folder)
      setPreview(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingPreview(false)
    }
  }

  async function confirmPush() {
    setError(null)
    try {
      const res = await api.createPlaylistExecute(folder)
      setJobId(res.job_id)
      setConfirmOpen(false)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-xl font-semibold text-slate-800 mb-1">
        Create Playlist
        <Help text="Schedules the uploaded content onto all 3 real screens (TV1, TV3, TV5) using the current schedule.csv. AbleSign rate-limits this to ~28 items/hour per screen, so a full push can take a couple hours - preview first to see exactly what will happen before pushing." />
      </h1>
      <p className="text-sm text-slate-500 mb-4">Always targets all 3 real screens (TV1/TV3/TV5) - the mapping is fixed.</p>

      {error && <div className="mb-3 text-sm text-red-600">{error}</div>}

      <label className="text-sm text-slate-600 block mb-1">Month folder (must already be uploaded)</label>
      <select
        value={selectedMonth}
        onChange={(e) => {
          setSelectedMonth(e.target.value)
          setPreview(null)
        }}
        className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm mb-4"
      >
        {months?.map((m) => (
          <option key={m.drive_id} value={m.name}>{m.name}</option>
        ))}
      </select>

      <button
        disabled={!selectedMonth || loadingPreview}
        onClick={loadPreview}
        className="px-4 py-2 rounded-md text-sm font-medium bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-40"
      >
        {loadingPreview ? 'Checking…' : 'Preview what would be pushed'}
      </button>

      {preview && (
        <div className="mt-5">
          <div className="text-sm text-slate-600 mb-3">
            <span className="font-semibold text-indigo-700">{preview.total_would_add}</span> item(s) would be added,{' '}
            <span className="font-semibold">{preview.total_already_present}</span> already present and would be skipped.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            {preview.screens.map((s) => (
              <div key={s.screen_id} className="border border-slate-200 rounded-lg p-3 bg-white">
                <div className="font-semibold text-sm text-slate-800">{s.tag} — {s.screen_title}</div>
                <div className="text-xs text-slate-500 mt-1">{s.would_add} to add · {s.already_present} already there</div>
                {s.items.length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-indigo-600 cursor-pointer">Show items</summary>
                    <div className="mt-1 max-h-40 overflow-y-auto text-xs text-slate-600 space-y-0.5">
                      {s.items.map((it, idx) => (
                        <div key={idx}>{it.class} — {it.day} {it.start}-{it.end}</div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))}
          </div>

          <button
            disabled={preview.total_would_add === 0}
            onClick={() => setConfirmOpen(true)}
            className="px-4 py-2 rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40"
          >
            Confirm & Push to AbleSign
          </button>
        </div>
      )}

      {jobId && (
        <div>
          <div className="text-xs text-slate-400 mt-4">Pushing live to AbleSign now - safe to leave this open, or close the tab and check back later, the job keeps running on the backend.</div>
          <JobLogPanel jobId={jobId} />
        </div>
      )}

      <ConfirmModal
        open={confirmOpen}
        title={`Push ${preview?.total_would_add ?? 0} item(s) to AbleSign?`}
        description="This writes live to TV1, TV3, and TV5. It can take a while due to AbleSign's rate limit, but it's safe to interrupt and restart - already-added items are never duplicated."
        confirmLabel="Push now"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmPush}
      >
        <div className="text-sm text-slate-600 space-y-1">
          {preview?.screens.map((s) => (
            <div key={s.screen_id}>{s.tag} — {s.screen_title}: <span className="font-medium">{s.would_add}</span> item(s)</div>
          ))}
        </div>
      </ConfirmModal>
    </div>
  )
}
